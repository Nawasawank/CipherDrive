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
import concurrent.futures

router = APIRouter()
load_dotenv()

def generate_unique_filename(base_name: str, user_id: str, existing_names: set) -> str:
    if base_name not in existing_names:
        return base_name
    name, ext = os.path.splitext(base_name)
    i = 1
    while f"{name} ({i}){ext}" in existing_names:
        i += 1
    return f"{name} ({i}){ext}"


@router.post("/upload")
async def upload_file(file: UploadFile, authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "user":
            raise HTTPException(status_code=403, detail="Only users with role 'user' can access this endpoint")
        user_id = decoded_token["user_id"]

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT is_locked, rsa_public_key FROM users WHERE id = %s", (user_id,))
                row = cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="User not found")
                is_locked, public_key = row

                if is_locked:
                    raise HTTPException(status_code=403, detail="Your account is locked due to suspicious activity")

                cursor.execute("SELECT file_name FROM files WHERE owner_id = %s", (user_id,))
                existing_names = {r[0] for r in cursor.fetchall()}

        file_name = generate_unique_filename(file.filename, user_id, existing_names)
        file_path = f"user_{user_id}/{file_name}"

        file_content = await file.read()
        aes_key = get_random_bytes(32)
        cipher = AES.new(aes_key, AES.MODE_EAX)
        nonce = cipher.nonce
        ciphertext, tag = cipher.encrypt_and_digest(file_content)
        full_data = nonce + tag + ciphertext

        encrypted_aes_key = await asyncio.to_thread(encrypt_rsa, public_key, aes_key.hex())

        bucket = "file"
        await asyncio.to_thread(supabase.storage.from_(bucket).upload, file_path, full_data)
        file_url = supabase.storage.from_(bucket).get_public_url(file_path)

        await asyncio.to_thread(
            lambda: supabase.table("files").insert({
                "owner_id": user_id,
                "file_name": file_name,
                "file_type": file.content_type,
                "file_url": file_url,
                "encrypted_aes_key": str(encrypted_aes_key)
            }).execute()
        )

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO user_activity_log (user_id, action, metadata) VALUES (%s, %s, %s)",
                    (user_id, 'upload', file_name)
                )

                cursor.execute("""
                    SELECT COUNT(*) FROM user_activity_log
                    WHERE user_id = %s AND action = 'upload' AND created_at > NOW() - INTERVAL '1 minute'
                """, (user_id,))
                upload_count = cursor.fetchone()[0]

                if upload_count > 100:
                    cursor.execute("UPDATE users SET is_locked = TRUE WHERE id = %s", (user_id,))
                    conn.commit()
                    raise HTTPException(
                        status_code=403,
                        detail="Your account is locked due to excessive uploads (more than 100 in 1 minute)."
                    )

                conn.commit()

        cipher = AES.new(aes_key, AES.MODE_EAX, nonce=nonce)
        decrypted = cipher.decrypt_and_verify(ciphertext, tag)

        decoded_content = (
            decrypted.decode("utf-8", errors="ignore")
            if file.content_type.startswith("text/")
            else base64.b64encode(decrypted).decode("utf-8")
        )

        return {
            "file": {
                "file_name": file_name,
                "file_type": file.content_type,
                "decrypted_content": decoded_content
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



process_pool = concurrent.futures.ProcessPoolExecutor()

@router.get("/my-files")
async def get_user_files(authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "user":
            raise HTTPException(status_code=403, detail="Only users with role 'user' can access this endpoint")
        user_id = decoded_token["user_id"]

        def get_user_info_and_records():
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT is_locked, email FROM users WHERE id = %s", (user_id,))
                    user_row = cursor.fetchone()
                    if not user_row:
                        raise HTTPException(status_code=404, detail="User not found")
                    is_locked, email = user_row
                    if is_locked:
                        raise HTTPException(status_code=403, detail="Your account is locked")

                    cursor.execute("""
                        SELECT u.email, f.file_name, f.file_type, f.file_url, f.encrypted_aes_key
                        FROM users u
                        JOIN files f ON u.id = f.owner_id
                        WHERE u.id = %s
                    """, (user_id,))
                    return email, cursor.fetchall()

        user_email, records = await asyncio.to_thread(get_user_info_and_records)
        if not records:
            return { "message": "No files found", "files": [] }

        prefix = f"USER_{user_email.upper().replace('@', '_').replace('.', '_')}"
        encrypted_private_key = os.getenv(f"{prefix}_ENCRYPTED_PRIVATE_KEY")
        aes_key_hex = os.getenv(f"{prefix}_AES_KEY")
        if not encrypted_private_key or not aes_key_hex:
            raise HTTPException(status_code=404, detail="Key not found in environment")

        private_key = await asyncio.to_thread(
            decrypt_private_key,
            encrypted_private_key,
            bytes.fromhex(aes_key_hex)
        )

        semaphore = asyncio.Semaphore(20)

        async def decrypt_file(file_data, client):
            _, file_name, file_type, file_url, encrypted_aes_key = file_data
            async with semaphore:
                decrypted_aes_key_hex = (await asyncio.get_running_loop().run_in_executor(
                    process_pool, decrypt_rsa, private_key, int(encrypted_aes_key)
                )).strip()
                aes_key = bytes.fromhex(decrypted_aes_key_hex)

                response = await client.get(file_url)
                response.raise_for_status()
                content = response.content

                nonce, tag, ciphertext = content[:16], content[16:32], content[32:]
                decrypted = await asyncio.to_thread(
                    lambda: AES.new(aes_key, AES.MODE_EAX, nonce).decrypt_and_verify(ciphertext, tag)
                )
                decoded_content = (
                    decrypted.decode("utf-8", errors="ignore")
                    if file_type.startswith("text/")
                    else base64.b64encode(decrypted).decode("utf-8")
                )
                return {
                    "file_name": file_name,
                    "file_type": file_type,
                    "decrypted_content": decoded_content
                }

        async with httpx.AsyncClient(timeout=10.0) as client:
            tasks = [decrypt_file(f, client) for f in records]
            decrypted_files = await asyncio.gather(*tasks)

        return {
            "message": "Files retrieved and decrypted successfully",
            "files": decrypted_files
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




# @router.get("/admin/all-files")
# async def admin_get_all_user_files(
#     authorization: str = Header(...),
#     page: int = Query(1, ge=1),
#     limit: int = Query(10, le=100)
# ):
#     try:
#         token = authorization.split(" ")[1]
#         decoded_token = verify_token(token)
#         if not decoded_token or decoded_token.get("role") != "admin":
#             raise HTTPException(status_code=403, detail="Admins only")

#         offset = (page - 1) * limit

#         with get_db() as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute("""
#                     SELECT u.id, u.email, f.file_name, f.file_type, f.file_url, f.encrypted_aes_key
#                     FROM files f
#                     JOIN users u ON f.owner_id = u.id
#                     ORDER BY u.email
#                     LIMIT %s OFFSET %s
#                 """, (limit, offset))
#                 files = cursor.fetchall()

#                 if not files:
#                     return {
#                         "message": "No files found",
#                         "success_files": [],
#                         "failed_files": [],
#                         "page": page,
#                         "limit": limit,
#                         "total_processed": 0
#                     }

#         key_cache = {}
#         semaphore = asyncio.Semaphore(10)

#         async def process_admin_file(record, client):
#             user_id, email, file_name, file_type, file_url, encrypted_aes_key = record
#             async with semaphore:
#                 try:
#                     if email not in key_cache:
#                         prefix = f"USER_{email.upper().replace('@', '_').replace('.', '_')}"
#                         enc_priv = os.getenv(f"{prefix}_ENCRYPTED_PRIVATE_KEY")
#                         aes_hex = os.getenv(f"{prefix}_AES_KEY")
#                         if not enc_priv or not aes_hex:
#                             raise Exception("Missing environment keys")
#                         private_key = await asyncio.to_thread(decrypt_private_key, enc_priv, bytes.fromhex(aes_hex))
#                         key_cache[email] = private_key
#                     else:
#                         private_key = key_cache[email]

#                     aes_key_hex_dec = (await asyncio.to_thread(decrypt_rsa, private_key, int(encrypted_aes_key))).strip()
#                     aes_key = bytes.fromhex(aes_key_hex_dec)

#                     response = await client.get(file_url)
#                     response.raise_for_status()

#                     content = response.content
#                     nonce, tag, ciphertext = content[:16], content[16:32], content[32:]

#                     cipher = AES.new(aes_key, AES.MODE_EAX, nonce=nonce)
#                     decrypted = cipher.decrypt_and_verify(ciphertext, tag)

#                     decoded = (
#                         decrypted.decode("utf-8", errors="ignore")
#                         if file_type.startswith("text/")
#                         else base64.b64encode(decrypted).decode("utf-8")
#                     )

#                     return {
#                         "user_email": email,
#                         "file_name": file_name,
#                         "file_type": file_type,
#                         "decrypted_content": decoded
#                     }

#                 except Exception as e:
#                     return {
#                         "user_email": email,
#                         "file_name": file_name,
#                         "file_type": file_type,
#                         "error": str(e)
#                     }

#         async with httpx.AsyncClient(timeout=5.0) as client:
#             tasks = [process_admin_file(record, client) for record in files]
#             results = await asyncio.gather(*tasks)

#         success_files = [res for res in results if "decrypted_content" in res and "error" not in res]
#         failed_files = [res for res in results if "error" in res]
#         total_processed = len(success_files) + len(failed_files)

#         return {
#             "message": "Files processed",
#             "success_files": success_files,
#             "failed_files": failed_files,
#             "page": page,
#             "limit": limit,
#             "total_processed": total_processed
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete-file")
async def delete_file(file_name: str, authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "user":
            raise HTTPException(status_code=403, detail="Only users with role 'user' can access this endpoint")

        user_id = decoded_token["user_id"]

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT is_locked FROM users WHERE id = %s", (user_id,))
                if cursor.fetchone()[0]:
                    raise HTTPException(status_code=403, detail="Your account is locked")

                cursor.execute("""
                    SELECT file_url FROM files WHERE file_name = %s AND owner_id = %s
                """, (file_name, user_id))
                row = cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="File not found")

                file_url = row[0]
                path_start = file_url.find("/file/") + len("/file/")
                file_path = file_url[path_start:]

                supabase.storage.from_("file").remove([file_path])

                cursor.execute("DELETE FROM files WHERE file_name = %s AND owner_id = %s", (file_name, user_id))
                conn.commit()

        return {"message": f"'{file_name}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

