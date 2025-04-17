from fastapi import APIRouter, UploadFile, HTTPException, Header, Query
import os
import base64
import asyncio
from dotenv import load_dotenv
import httpx
from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes
from supabase_client import supabase
from utils.aes import decrypt_private_key
from utils.rsa import encrypt_rsa, decrypt_rsa
from utils.jwt_handler import verify_token
from db import get_db

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
                    LIMIT 100
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
                    cursor.execute("UPDATE users SET is_locked = TRUE WHERE id = %s", (u[0],))
                    blocked_users.append(u[1])

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
                    cursor.execute("UPDATE users SET is_locked = TRUE WHERE id = %s", (u[0],))
                    blocked_users.append(u[1])

                # Failed Login Attempts
                cursor.execute("""
                    SELECT u.id, u.email, COUNT(*) as failed_logins, array_agg(a.metadata), MIN(a.created_at), MAX(a.created_at)
                    FROM user_activity_log a
                    JOIN users u ON a.user_id = u.id
                    WHERE a.action = 'failed_login' AND a.created_at > NOW() - INTERVAL '1 hour'
                    GROUP BY u.id, u.email
                    HAVING COUNT(*) > 3
                """)
                failed_logins = cursor.fetchall()

                for u in failed_logins:
                    cursor.execute("UPDATE users SET is_locked = TRUE WHERE id = %s", (u[0],))
                    blocked_users.append(u[1])

                conn.commit()

        return {
            "blocked_users": blocked_users,
            "message": "Suspicious users have been blocked."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
