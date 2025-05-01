from fastapi import APIRouter, HTTPException, Header
from db import get_db
from utils.jwt_handler import verify_token
from utils.rsa import encrypt_rsa, decrypt_rsa
from utils.aes import decrypt_private_key
from schemas.share import ShareFileRequest
from Cryptodome.Cipher import AES
import requests
import base64
import httpx
import asyncio
import os

router = APIRouter()

@router.post("/share-file")
async def share_file(payload: ShareFileRequest, authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "user":
            raise HTTPException(status_code=403, detail="Only users with role 'user' can access this endpoint")

        owner_id = decoded_token["user_id"]
        file_name = payload.file_name
        shared_with_email = payload.shared_with_email

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT is_locked, email FROM users WHERE id = %s", (owner_id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="User not found")
                is_locked, owner_email = row
                if is_locked:
                    raise HTTPException(status_code=403, detail="Your account is locked")

                cur.execute(
                    "SELECT id, encrypted_aes_key FROM files WHERE file_name = %s AND owner_id = %s",
                    (file_name, owner_id),
                )
                file_record = cur.fetchone()
                if not file_record:
                    raise HTTPException(status_code=404, detail="File not found or no permission")
                file_id, encrypted_aes_key = file_record

                cur.execute("SELECT id, rsa_public_key, role FROM users WHERE email = %s", (shared_with_email,))
                recipient = cur.fetchone()
                if not recipient:
                    raise HTTPException(status_code=404, detail="Recipient user not found")
                recipient_id, recipient_public_key, recipient_role = recipient

                if recipient_role == "admin":
                    raise HTTPException(status_code=403, detail="You cannot share files with an admin account")

        env_key_prefix = f"USER_{owner_email.upper().replace('@', '_').replace('.', '_')}"
        encrypted_private_key = os.getenv(f"{env_key_prefix}_ENCRYPTED_PRIVATE_KEY")
        aes_key_hex = os.getenv(f"{env_key_prefix}_AES_KEY")
        if not encrypted_private_key or not aes_key_hex:
            raise HTTPException(status_code=404, detail="Owner key not found in env")

        owner_aes_key = bytes.fromhex(aes_key_hex)
        owner_private_key = decrypt_private_key(encrypted_private_key, owner_aes_key)

        original_aes_key_hex = decrypt_rsa(owner_private_key, int(encrypted_aes_key))
        encrypted_aes_key_for_recipient = encrypt_rsa(recipient_public_key, original_aes_key_hex)

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO shared_files (file_id, shared_with, encrypted_aes_key)
                    VALUES (%s, %s, %s)
                    """,
                    (file_id, recipient_id, encrypted_aes_key_for_recipient),
                )

                cur.execute(
                    "INSERT INTO user_activity_log (user_id, action, metadata) VALUES (%s, %s, %s)",
                    (owner_id, 'share', shared_with_email)
                )

                cur.execute("""
                    SELECT COUNT(DISTINCT metadata)
                    FROM user_activity_log
                    WHERE user_id = %s AND action = 'share' AND created_at > NOW() - INTERVAL '1 minute'
                """, (owner_id,))
                unique_shares = cur.fetchone()[0]
                print(f"Unique shares in the last minute: {unique_shares}")

                if unique_shares > 50:
                    cur.execute("UPDATE users SET is_locked = TRUE WHERE id = %s", (owner_id,))
                    conn.commit()
                    raise HTTPException(
                        status_code=403,
                        detail="Your account is locked due to excessive sharing (more than 50 unique shares in 1 minute)."
                    )
                conn.commit()

        return {"message": "File shared successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shared-files")
async def get_shared_files(authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "user":
            raise HTTPException(status_code=403, detail="Only users with role 'user' can access this endpoint")

        user_id = decoded_token["user_id"]

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT is_locked, email FROM users WHERE id = %s", (user_id,))
                row = cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="User not found")
                is_locked, user_email = row
                if is_locked:
                    raise HTTPException(status_code=403, detail="Your account is locked")

                cursor.execute("""
                    SELECT u.email, f.file_name, f.file_type, f.file_url,
                           sf.encrypted_aes_key, o.email AS owner_email
                    FROM shared_files sf
                    JOIN files f ON sf.file_id = f.id
                    JOIN users u ON sf.shared_with = u.id
                    JOIN users o ON f.owner_id = o.id
                    WHERE sf.shared_with = %s
                """, (user_id,))
                result = cursor.fetchall()

                if not result:
                    return {
                        "message": "No shared files found",
                        "shared_files": []
                    }

                shared_files = result

        prefix = f"USER_{user_email.upper().replace('@', '_').replace('.', '_')}"
        encrypted_private_key = os.getenv(f"{prefix}_ENCRYPTED_PRIVATE_KEY")
        aes_key_hex = os.getenv(f"{prefix}_AES_KEY")
        if not encrypted_private_key or not aes_key_hex:
            raise HTTPException(status_code=404, detail="Missing decryption keys")

        private_key = await asyncio.to_thread(decrypt_private_key, encrypted_private_key, bytes.fromhex(aes_key_hex))

        semaphore = asyncio.Semaphore(10)

        async def process_shared_file(file, client):
            file_name, file_type, file_url, encrypted_aes_key, owner_email = file[1:]
            async with semaphore:
                try:
                    aes_key_hex = (await asyncio.to_thread(decrypt_rsa, private_key, int(encrypted_aes_key))).strip()
                    aes_key = bytes.fromhex(aes_key_hex)

                    response = await client.get(file_url)
                    response.raise_for_status()

                    content = response.content
                    nonce, tag, ciphertext = content[:16], content[16:32], content[32:]

                    cipher = AES.new(aes_key, AES.MODE_EAX, nonce=nonce)
                    decrypted = cipher.decrypt_and_verify(ciphertext, tag)

                    decoded = (
                        decrypted.decode("utf-8", errors="ignore")
                        if file_type.startswith("text/")
                        else base64.b64encode(decrypted).decode("utf-8")
                    )

                    return {
                        "file_name": file_name,
                        "file_type": file_type,
                        "decrypted_content": decoded,
                        "owner_email": owner_email,
                    }

                except Exception as e:
                    return {
                        "file_name": file_name,
                        "file_type": file_type,
                        "owner_email": owner_email,
                        "error": f"Error decrypting: {str(e)}"
                    }

        async with httpx.AsyncClient(timeout=10.0) as client:
            tasks = [process_shared_file(f, client) for f in shared_files]
            decrypted_files = await asyncio.gather(*tasks)

        return {
            "message": "Shared files retrieved and decrypted successfully",
            "shared_files": decrypted_files
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
