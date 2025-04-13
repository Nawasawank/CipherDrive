from fastapi import APIRouter, UploadFile, HTTPException, Header, Query
from supabase_client import supabase
from utils.aes import decrypt_private_key, generate_aes_key
from utils.rsa import encrypt_rsa, decrypt_rsa
from utils.jwt_handler import verify_token
from db import get_db
import base64
import os
import requests
import httpx
from dotenv import load_dotenv
from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes

router = APIRouter()
load_dotenv()

def generate_unique_filename(base_name: str, user_id: str) -> str:
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT file_name FROM files WHERE owner_id = %s", (user_id,))
            existing_names = {row[0] for row in cursor.fetchall()}

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
        if not decoded_token:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        user_id = decoded_token["user_id"]

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT rsa_public_key FROM users WHERE id = %s", (user_id,))
                result = cursor.fetchone()
                if not result:
                    raise HTTPException(status_code=404, detail="User not found")
                public_key = result[0]

        file_name = generate_unique_filename(file.filename, user_id)

        aes_key = get_random_bytes(32)
        file_content = await file.read()
        cipher = AES.new(aes_key, AES.MODE_EAX)
        nonce = cipher.nonce
        ciphertext, tag = cipher.encrypt_and_digest(file_content)
        full_data = nonce + tag + ciphertext

        encrypted_aes_key = encrypt_rsa(public_key, aes_key.hex())

        bucket = "file"
        supabase.storage.from_(bucket).upload(file_name, full_data)
        file_url = supabase.storage.from_(bucket).get_public_url(file_name)

        supabase.table("files").insert({
            "owner_id": user_id,
            "file_name": file_name,
            "file_type": file.content_type,
            "file_url": file_url,
            "encrypted_aes_key": str(encrypted_aes_key)
        }).execute()

        return {
            "message": "File uploaded successfully",
            "file_url": file_url,
            "encrypted_aes_key": str(encrypted_aes_key),
            "final_file_name": file_name
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/my-files")
async def get_user_files(authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        user_id = decoded_token["user_id"]

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT email FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")
                user_email = user[0]

                env_key_prefix = f"USER_{user_email.upper().replace('@', '_').replace('.', '_')}"
                encrypted_private_key = os.getenv(f"{env_key_prefix}_ENCRYPTED_PRIVATE_KEY")
                aes_key_hex = os.getenv(f"{env_key_prefix}_AES_KEY")
                if not encrypted_private_key or not aes_key_hex:
                    raise HTTPException(status_code=404, detail="Key not found in environment")

                private_key = decrypt_private_key(encrypted_private_key, bytes.fromhex(aes_key_hex))

                cursor.execute("""
                    SELECT file_name, file_type, file_url, encrypted_aes_key 
                    FROM files 
                    WHERE owner_id = %s
                """, (user_id,))
                files = cursor.fetchall()

        decrypted_files = []

        for file in files:
            file_name, file_type, file_url, encrypted_aes_key = file
            try:
                aes_key_hex = decrypt_rsa(private_key, int(encrypted_aes_key)).strip()
                aes_key = bytes.fromhex(aes_key_hex)

                response = requests.get(file_url)
                if response.status_code != 200:
                    raise Exception("Failed to download encrypted file")

                content = response.content
                nonce = content[:16]
                tag = content[16:32]
                ciphertext = content[32:]

                cipher = AES.new(aes_key, AES.MODE_EAX, nonce=nonce)
                decrypted = cipher.decrypt_and_verify(ciphertext, tag)

                if file_type.startswith("text/"):
                    decoded = decrypted.decode("utf-8", errors="ignore")
                else:
                    decoded = base64.b64encode(decrypted).decode("utf-8")

                decrypted_files.append({
                    "file_name": file_name,
                    "file_type": file_type,
                    "decrypted_content": decoded
                })

            except Exception as e:
                decrypted_files.append({
                    "file_name": file_name,
                    "file_type": file_type,
                    "decrypted_content": f"Error decrypting: {str(e)}"
                })

        return {
            "message": "Files retrieved and decrypted successfully",
            "files": decrypted_files
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/all-files")
async def admin_get_all_user_files(
    authorization: str = Header(...),
    page: int = Query(1, ge=1),
    limit: int = Query(10, le=100)
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
                    SELECT u.id, u.email, f.file_name, f.file_type, f.file_url, f.encrypted_aes_key
                    FROM files f
                    JOIN users u ON f.owner_id = u.id
                    ORDER BY u.email
                    LIMIT %s OFFSET %s
                """, (limit, offset))
                files = cursor.fetchall()

        key_cache = {}
        results = []
        failed = []

        async with httpx.AsyncClient() as client:
            for user_id, email, file_name, file_type, file_url, encrypted_aes_key in files:
                try:
                    if email not in key_cache:
                        prefix = f"USER_{email.upper().replace('@', '_').replace('.', '_')}"
                        enc_priv = os.getenv(f"{prefix}_ENCRYPTED_PRIVATE_KEY")
                        aes_hex = os.getenv(f"{prefix}_AES_KEY")
                        if not enc_priv or not aes_hex:
                            raise Exception("Missing environment keys")
                        key_cache[email] = (enc_priv, aes_hex)

                    encrypted_private_key, aes_key_hex = key_cache[email]
                    private_key = decrypt_private_key(encrypted_private_key, bytes.fromhex(aes_key_hex))

                    aes_key_hex_dec = decrypt_rsa(private_key, int(encrypted_aes_key)).strip()
                    aes_key = bytes.fromhex(aes_key_hex_dec)

                    response = await client.get(file_url)
                    if response.status_code != 200:
                        raise Exception("Failed to download file")

                    content = response.content
                    nonce = content[:16]
                    tag = content[16:32]
                    ciphertext = content[32:]

                    cipher = AES.new(aes_key, AES.MODE_EAX, nonce=nonce)
                    decrypted = cipher.decrypt_and_verify(ciphertext, tag)

                    if file_type.startswith("text/"):
                        decoded = decrypted.decode("utf-8", errors="ignore")
                    else:
                        decoded = base64.b64encode(decrypted).decode("utf-8")

                    results.append({
                        "user_email": email,
                        "file_name": file_name,
                        "file_type": file_type,
                        "decrypted_content": decoded
                    })

                except Exception as e:
                    failed.append({
                        "user_email": email,
                        "file_name": file_name,
                        "file_type": file_type,
                        "error": str(e)
                    })

        return {
            "message": "Files processed",
            "success_files": results,
            "failed_files": failed,
            "page": page,
            "limit": limit,
            "total_processed": len(results) + len(failed)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
