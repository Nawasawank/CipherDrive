# routers/files.py

from fastapi import APIRouter, UploadFile, HTTPException, Form
from supabase_client import supabase
from utils.aes import BLOCK_SIZE
from utils.rsa import encrypt_rsa
from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes
from Cryptodome.Util.Padding import pad
import tempfile

router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile, user_email: str = Form(...)):
    try:
        user_query = supabase.table("users").select("id, rsa_public_key").eq("email", user_email).single().execute()
        user = user_query.data
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user_id = user["id"]
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
