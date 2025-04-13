# routers/files.py

from fastapi import APIRouter, UploadFile, HTTPException, Form, Header
from supabase_client import supabase
from utils.aes import BLOCK_SIZE
from utils.rsa import encrypt_rsa
from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes
from Cryptodome.Util.Padding import pad, unpad
import requests
from utils.jwt_handler import verify_token
from utils.rsa import decrypt_rsa
from utils.aes import BLOCK_SIZE, decrypt_private_key
from Cryptodome.Cipher import AES
import os
from dotenv import load_dotenv
from db import cursor, conn
import base64

router = APIRouter()

load_dotenv

@router.post("/upload")
async def upload_file( file: UploadFile, authorization: str = Header(...),):
    try:
        token = authorization.split(" ")[1]

        decoded_token = verify_token(token)
        if not decoded_token:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        user_id = decoded_token["user_id"]

        user_query = supabase.table("users").select("rsa_public_key").eq("id", user_id).single().execute()
        user = user_query.data
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        public_key = user["rsa_public_key"]

        aes_key = get_random_bytes(32)


        file_content = await file.read()
        iv = get_random_bytes(16)
        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        encrypted_content = cipher.encrypt(pad(file_content, BLOCK_SIZE))


        encrypted_aes_key = encrypt_rsa(public_key, aes_key.hex())

        bucket = "file"
        file_path = file.filename
        full_data = iv + encrypted_content

        supabase.storage.from_(bucket).upload(file_path, full_data)
        file_url = supabase.storage.from_(bucket).get_public_url(file_path)

        supabase.table("files").insert({
            "owner_id": user_id,
            "file_name": file.filename,
            "file_type": file.content_type,
            "file_url": file_url,
            "encrypted_aes_key": str(encrypted_aes_key)
        }).execute()

        return {
            "message": "File uploaded successfully",
            "file_url": file_url,
            "encrypted_aes_key": str(encrypted_aes_key)
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
                raise HTTPException(status_code=404, detail="Encrypted key not found in environment")

            aes_key = bytes.fromhex(aes_key_hex)
            private_key = decrypt_private_key(encrypted_private_key, aes_key)

            cursor.execute("SELECT file_name, file_type, file_url, encrypted_aes_key FROM files WHERE owner_id = %s", (user_id,))
            files = cursor.fetchall()

        decrypted_files = []
        for file in files:
            file_name, file_type, file_url, encrypted_aes_key = file

            aes_key_hex = decrypt_rsa(private_key, int(encrypted_aes_key))
            aes_key = bytes.fromhex(aes_key_hex)

            encrypted_file_response = requests.get(file_url)
            if encrypted_file_response.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to download encrypted file")

            encrypted_file_content = encrypted_file_response.content
            iv = encrypted_file_content[:16]
            ciphertext = encrypted_file_content[16:]

            cipher = AES.new(aes_key, AES.MODE_CBC, iv)
            decrypted_content = unpad(cipher.decrypt(ciphertext), BLOCK_SIZE)

            if file_type.startswith("text/"):
                content = decrypted_content.decode("utf-8", errors="ignore")
            else:
                content = base64.b64encode(decrypted_content).decode("utf-8")

            decrypted_files.append({
                "file_name": file_name,
                "file_type": file_type,
                "decrypted_content": content
            })

        return {
            "message": "Files retrieved and decrypted successfully",
            "files": decrypted_files
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))