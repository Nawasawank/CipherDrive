from fastapi import APIRouter, UploadFile, HTTPException, Header, Query
from dotenv import load_dotenv
from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes
from supabase_client import supabase
from utils.aes import decrypt_private_key
from utils.rsa import encrypt_rsa, decrypt_rsa
from utils.jwt_handler import verify_token
from db import get_db
from datetime import datetime
from typing import Optional

router = APIRouter()

@router.get("/stats")
async def get_admin_stats(authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admins only")

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM files")
                total_uploads = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM shared_files")
                total_shares = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT u.email, COUNT(f.id) as upload_count
                    FROM users u
                    LEFT JOIN files f ON u.id = f.owner_id
                    WHERE u.role = 'user'
                    GROUP BY u.email
                """)
                upload_per_user = cursor.fetchall()

                cursor.execute("""
                    SELECT u.email, COUNT(sf.id) as shared_count
                    FROM users u
                    LEFT JOIN files f ON u.id = f.owner_id
                    LEFT JOIN shared_files sf ON f.id = sf.file_id
                    WHERE u.role = 'user'
                    GROUP BY u.email
                """)
                share_per_user = cursor.fetchall()

        return {
            "total_uploads": total_uploads,
            "total_shares": total_shares,
            "uploads_per_user": upload_per_user,
            "shares_per_user": share_per_user
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users")
async def get_all_users(authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)

        if not decoded_token or decoded_token.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admins only")

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, email FROM users WHERE role = 'user' ORDER BY email")
                users = cursor.fetchall()

        return {
            "message": "Users retrieved successfully",
            "users": [{"id": u[0], "email": u[1]} for u in users]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/activity-log")
async def get_activity_log(authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admins only")

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT u.email, a.action, a.metadata, a.created_at
                    FROM user_activity_log a
                    LEFT JOIN users u ON a.user_id = u.id
                    ORDER BY a.created_at DESC
                """)
                logs = cursor.fetchall()

                enriched_logs = []
                for log in logs:
                    actor_email, action, metadata, timestamp = log

                    if action == 'share':
                        cursor.execute("""
                            SELECT f.file_name, ru.email AS recipient_email
                            FROM files f
                            JOIN shared_files sf ON f.id = sf.file_id
                            JOIN users ru ON sf.shared_with = ru.id
                            WHERE f.file_name = %s OR ru.email = %s
                            LIMIT 1
                        """, (metadata, metadata))
                        result = cursor.fetchone()
                        if result:
                            file_name, recipient_email = result
                            metadata_display = f"shared '{file_name}' with {recipient_email}"
                        else:
                            metadata_display = f"shared with unknown ({metadata})"
                    else:
                        metadata_display = metadata

                    enriched_logs.append({
                        "email": actor_email,
                        "action": action,
                        "metadata": metadata_display,
                        "timestamp": timestamp.isoformat()
                    })

        return {
            "message": "Recent activity log",
            "logs": enriched_logs
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suspicious-activity")
async def get_suspicious_activity(authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admins only")

        blocked_users = []
        suspicious_summary = []

        with get_db() as conn:
            with conn.cursor() as cursor:

                # Fast Uploaders
                cursor.execute("""
                    SELECT u.id, u.email, COUNT(*) as upload_count, MIN(a.created_at), MAX(a.created_at)
                    FROM user_activity_log a
                    JOIN users u ON a.user_id = u.id
                    WHERE a.action = 'upload' AND a.created_at > NOW() - INTERVAL '1 minute'
                    GROUP BY u.id, u.email
                    HAVING COUNT(*) > 100
                """)
                fast_uploaders = cursor.fetchall()

                for u in fast_uploaders:
                    cursor.execute("SELECT is_locked FROM users WHERE id = %s", (u[0],))
                    if cursor.fetchone()[0]:  # If already locked
                        blocked_users.append(u[1])
                    suspicious_summary.append({
                        "email": u[1],
                        "action": "upload",
                        "count": u[2],
                        "first_seen": u[3].isoformat(),
                        "last_seen": u[4].isoformat()
                    })

                # Oversharers
                cursor.execute("""
                    SELECT u.id, u.email, COUNT(DISTINCT a.metadata) as unique_shares, MIN(a.created_at), MAX(a.created_at)
                    FROM user_activity_log a
                    JOIN users u ON a.user_id = u.id
                    WHERE a.action = 'share'
                    GROUP BY u.id, u.email
                    HAVING COUNT(DISTINCT a.metadata) > 50
                """)
                oversharers = cursor.fetchall()

                for u in oversharers:
                    cursor.execute("SELECT is_locked FROM users WHERE id = %s", (u[0],))
                    if cursor.fetchone()[0]:
                        blocked_users.append(u[1])
                    suspicious_summary.append({
                        "email": u[1],
                        "action": "share",
                        "count": u[2],
                        "first_seen": u[3].isoformat(),
                        "last_seen": u[4].isoformat()
                    })

                cursor.execute("""
                    SELECT u.id, u.email, COUNT(*) as failed_logins, MIN(a.created_at), MAX(a.created_at)
                    FROM user_activity_log a
                    JOIN users u ON a.user_id = u.id
                    WHERE a.action = 'failed_login' AND a.created_at > NOW() - INTERVAL '1 hour'
                    GROUP BY u.id, u.email
                    HAVING COUNT(*) > 3
                """)
                failed_logins = cursor.fetchall()

                for u in failed_logins:
                    cursor.execute("SELECT is_locked FROM users WHERE id = %s", (u[0],))
                    if cursor.fetchone()[0]:
                        blocked_users.append(u[1])
                    suspicious_summary.append({
                        "email": u[1],
                        "action": "failed_login",
                        "count": u[2],
                        "first_seen": u[3].isoformat(),
                        "last_seen": u[4].isoformat()
                    })

        return {
            "blocked_users": blocked_users,
            "message": "Suspicious activity detected.",
            "suspicious_summary": suspicious_summary
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    

@router.get("/user-activity")
async def get_user_activity(
    email: str,
    authorization: str = Header(...)
):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admins only")

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT u.email, a.action, a.metadata, a.created_at
                    FROM user_activity_log a
                    JOIN users u ON a.user_id = u.id
                    WHERE u.email = %s
                    ORDER BY a.created_at DESC
                """, (email,))
                logs = cursor.fetchall()

        return {
            "email": email,
            "logs": [
                {
                    "action": row[1],
                    "metadata": row[2],
                    "timestamp": row[3].isoformat()
                } for row in logs
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/search-users")
async def search_users(
    query: str = Query(...),
    authorization: str = Header(...)
):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admins only")

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, email FROM users
                    WHERE role = 'user' AND email ILIKE %s
                    ORDER BY email
                """, (f"%{query}%",))
                results = cursor.fetchall()

        return {
            "users": [{"id": r[0], "email": r[1]} for r in results]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/filter-activity")
async def filter_activity(
    action_type: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    authorization: str = Header(...)
):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admins only")

        filters = []
        values = []

        if action_type:
            filters.append("a.action = %s")
            values.append(action_type)

        if date:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                filters.append("DATE(a.created_at) = %s")
                values.append(date_obj.date())
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        query = """
            SELECT u.email, a.action, a.metadata, a.created_at
            FROM user_activity_log a
            JOIN users u ON a.user_id = u.id
        """

        if filters:
            query += " WHERE " + " AND ".join(filters)

        query += " ORDER BY a.created_at DESC"

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, tuple(values))
                logs = cursor.fetchall()

        return {
            "logs": [
                {
                    "email": row[0],
                    "action": row[1],
                    "metadata": row[2],
                    "timestamp": row[3].isoformat()
                } for row in logs
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.put("/lock-user")
async def lock_user(email: str = Query(...), authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admins only")

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE users SET is_locked = TRUE WHERE email = %s", (email,))
                conn.commit()

        return {"message": f"User '{email}' has been locked"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.put("/unlock-user")
async def unlock_user(email: str = Query(...), authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admins only")

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE users SET is_locked = FALSE WHERE email = %s", (email,))
                conn.commit()

        return {"message": f"User '{email}' has been unlocked"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


