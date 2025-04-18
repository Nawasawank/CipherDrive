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
from datetime import datetime, timedelta

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
async def get_all_users(
    authorization: str = Header(...),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100)
):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)

        if not decoded_token or decoded_token.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admins only")

        offset = (page - 1) * limit

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'user'")
                total_users = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT id, email
                    FROM users
                    WHERE role = 'user'
                    ORDER BY email
                    LIMIT %s OFFSET %s
                """, (limit, offset))
                users = cursor.fetchall()

        return {
            "message": "Users retrieved successfully",
            "page": page,
            "limit": limit,
            "total": total_users,
            "users": [{"id": u[0], "email": u[1]} for u in users]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/allactivity")
async def get_all_activity(authorization: str = Header(...)):
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
            "message": "All activity logs",
            "logs": enriched_logs
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/activity-log")
async def get_activity_log(
    authorization: str = Header(...),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100)
):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admins only")

        offset = (page - 1) * limit

        with get_db() as conn:
            with conn.cursor() as cursor:
                # Get total count for pagination
                cursor.execute("SELECT COUNT(*) FROM user_activity_log")
                total_logs = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT u.email, a.action, a.metadata, a.created_at
                    FROM user_activity_log a
                    LEFT JOIN users u ON a.user_id = u.id
                    ORDER BY a.created_at DESC
                    LIMIT %s OFFSET %s
                """, (limit, offset))
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
            "page": page,
            "limit": limit,
            "total": total_logs,
            "logs": enriched_logs
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suspicious-activity")
async def get_suspicious_activity(
    authorization: str = Header(...),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admins only")

        blocked_users = []
        suspicious_summary = []

        date_filter = ""
        params = []

        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                date_filter += " AND a.created_at >= %s"
                params.append(start_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD.")

        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                date_filter += " AND a.created_at < %s"
                params.append(end_dt.strftime("%Y-%m-%d"))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD.")

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, email FROM users WHERE is_locked = TRUE")
                locked_result = cursor.fetchall()
                locked_users = {row[0]: row[1] for row in locked_result}
                blocked_users = list(locked_users.values())

                cursor.execute(f"""
                    SELECT u.id, u.email, COUNT(*) AS count, MIN(a.created_at), MAX(a.created_at)
                    FROM user_activity_log a
                    JOIN users u ON u.id = a.user_id
                    WHERE a.action = 'upload' {date_filter}
                    GROUP BY u.id, u.email
                    HAVING COUNT(*) > 100
                """, params)
                for user_id, email, count, first_seen, last_seen in cursor.fetchall():
                    suspicious_summary.append({
                        "email": email,
                        "action": "upload",
                        "count": count,
                        "first_seen": first_seen.isoformat(),
                        "last_seen": last_seen.isoformat(),
                        "is_locked": user_id in locked_users
                    })

                cursor.execute(f"""
                    SELECT u.id, u.email, COUNT(DISTINCT a.metadata) AS count, MIN(a.created_at), MAX(a.created_at)
                    FROM user_activity_log a
                    JOIN users u ON u.id = a.user_id
                    WHERE a.action = 'share' {date_filter}
                    GROUP BY u.id, u.email
                    HAVING COUNT(DISTINCT a.metadata) > 50
                """, params)
                for user_id, email, count, first_seen, last_seen in cursor.fetchall():
                    suspicious_summary.append({
                        "email": email,
                        "action": "share",
                        "count": count,
                        "first_seen": first_seen.isoformat(),
                        "last_seen": last_seen.isoformat(),
                        "is_locked": user_id in locked_users
                    })

                cursor.execute(f"""
                    SELECT DISTINCT u.id, u.email
                    FROM user_activity_log a1
                    JOIN user_activity_log a2 ON a1.user_id = a2.user_id
                    JOIN user_activity_log a3 ON a1.user_id = a3.user_id
                    JOIN users u ON u.id = a1.user_id
                    WHERE a1.action = 'failed_login'
                      AND a2.action = 'failed_login'
                      AND a3.action = 'failed_login'
                      AND a1.created_at < a2.created_at
                      AND a2.created_at < a3.created_at
                      AND a3.created_at <= a1.created_at + INTERVAL '1 minute'
                      {date_filter.replace('a.', 'a1.')}
                """, params)
                failed_logins = cursor.fetchall()

                for user_id, email in failed_logins:
                    cursor.execute(f"""
                        SELECT COUNT(*), MIN(created_at), MAX(created_at)
                        FROM user_activity_log
                        WHERE user_id = %s AND action = 'failed_login' {date_filter.replace('a.', '')}
                    """, [user_id] + params)
                    count, first_seen, last_seen = cursor.fetchone()
                    suspicious_summary.append({
                        "email": email,
                        "action": "failed_login",
                        "count": count,
                        "first_seen": first_seen.isoformat() if first_seen else None,
                        "last_seen": last_seen.isoformat() if last_seen else None,
                        "is_locked": user_id in locked_users
                    })

        start = (page - 1) * limit
        end = start + limit
        paginated_summary = suspicious_summary[start:end]

        return {
            "blocked_users": blocked_users,
            "message": "Suspicious activity detected.",
            "total": len(suspicious_summary),
            "page": page,
            "limit": limit,
            "suspicious_summary": paginated_summary
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    

@router.get("/user-activity")
async def get_user_activity(
    email: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    authorization: str = Header(...)
):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admins only")

        offset = (page - 1) * limit

        with get_db() as conn:
            with conn.cursor() as cursor:
                # Get total count
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM user_activity_log a
                    JOIN users u ON a.user_id = u.id
                    WHERE u.email = %s
                """, (email,))
                total_logs = cursor.fetchone()[0]

                # Fetch paginated logs
                cursor.execute("""
                    SELECT a.action, a.metadata, a.created_at
                    FROM user_activity_log a
                    JOIN users u ON a.user_id = u.id
                    WHERE u.email = %s
                    ORDER BY a.created_at DESC
                    LIMIT %s OFFSET %s
                """, (email, limit, offset))
                logs = cursor.fetchall()

        return {
            "email": email,
            "page": page,
            "limit": limit,
            "total": total_logs,
            "logs": [
                {
                    "action": row[0],
                    "metadata": row[1],
                    "timestamp": row[2].isoformat()
                } for row in logs
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    
@router.get("/search-users")
async def search_users(
    query: str = Query(...),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    authorization: str = Header(...)
):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admins only")

        offset = (page - 1) * limit

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) FROM users
                    WHERE role = 'user' AND email ILIKE %s
                """, (f"%{query}%",))
                total_users = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT id, email FROM users
                    WHERE role = 'user' AND email ILIKE %s
                    ORDER BY email
                    LIMIT %s OFFSET %s
                """, (f"%{query}%", limit, offset))
                results = cursor.fetchall()

        return {
            "page": page,
            "limit": limit,
            "total": total_users,
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


