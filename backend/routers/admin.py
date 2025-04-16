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

@router.get("/user-files")
async def get_files_by_user(user_id: str = Query(...), authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token or decoded_token.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admins only")
        
        def query_files():
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT u.email, f.file_name, f.file_type, f.file_url, f.encrypted_aes_key
                        FROM users u
                        JOIN files f ON u.id = f.owner_id
                        WHERE u.id = %s AND role = 'user'
                    """, (user_id,))
                    return cursor.fetchall()
        records = await asyncio.to_thread(query_files)
        if not records:
            return {"message": "No files found", "files": []}

        user_email, *_ = records[0]
        
        prefix = f"USER_{user_email.upper().replace('@', '_').replace('.', '_')}"
        encrypted_private_key = os.getenv(f"{prefix}_ENCRYPTED_PRIVATE_KEY")
        aes_key_hex = os.getenv(f"{prefix}_AES_KEY")
        if not encrypted_private_key or not aes_key_hex:
            raise HTTPException(status_code=404, detail="Missing keys for user")
        
        private_key = await asyncio.to_thread(
            decrypt_private_key,
            encrypted_private_key,
            bytes.fromhex(aes_key_hex)
        )
        
        semaphore = asyncio.Semaphore(10)
        
        async def process_file(record, client: httpx.AsyncClient):
            _, file_name, file_type, file_url, encrypted_aes_key = record
            async with semaphore:
                try:
                    loop = asyncio.get_running_loop()
                    decrypted_aes_key_hex = (await loop.run_in_executor(
                        None, decrypt_rsa, private_key, int(encrypted_aes_key)
                    )).strip()
                    aes_key = bytes.fromhex(decrypted_aes_key_hex)
                    
                    response = await client.get(file_url)
                    response.raise_for_status()
                    content = response.content
                    
                    nonce, tag, ciphertext = content[:16], content[16:32], content[32:]
                    decrypted = await asyncio.to_thread(
                        lambda: AES.new(aes_key, AES.MODE_EAX, nonce=nonce).decrypt_and_verify(ciphertext, tag)
                    )
                    
                    decoded = (
                        decrypted.decode("utf-8", errors="ignore")
                        if file_type.startswith("text/")
                        else base64.b64encode(decrypted).decode("utf-8")
                    )
                    
                    return {
                        "file_name": file_name,
                        "file_type": file_type,
                        "decrypted_content": decoded
                    }
                except Exception as e:
                    return {
                        "file_name": file_name,
                        "file_type": file_type,
                        "error": str(e)
                    }
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            tasks = [process_file(record, client) for record in records]
            decrypted_files = await asyncio.gather(*tasks)
        
        return {
            "message": "Files retrieved",
            "files": decrypted_files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

