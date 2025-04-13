from fastapi import APIRouter, HTTPException, Header, Form
from db import conn
from utils.jwt_handler import verify_token
from utils.rsa import encrypt_rsa
import os
from schemas.share import ShareFileRequest
router = APIRouter()
import requests
from utils.aes import decrypt_private_key, BLOCK_SIZE
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import unpad
import base64
from utils.rsa import decrypt_rsa

@router.post("/share-file")
async def share_file(payload: ShareFileRequest, authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        owner_id = decoded_token["user_id"]

        file_name = payload.file_name
        shared_with_email = payload.shared_with_email
        permission = payload.permission

        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, encrypted_aes_key FROM files WHERE file_name = %s AND owner_id = %s",
                (file_name, owner_id),
            )
            file_record = cur.fetchone()
            if not file_record:
                raise HTTPException(
                    status_code=404,
                    detail="File not found or you do not have permission to share it"
                )
            file_id, encrypted_aes_key = file_record

            cur.execute("SELECT id, rsa_public_key FROM users WHERE email = %s", (shared_with_email,))
            recipient = cur.fetchone()
            if not recipient:
                raise HTTPException(status_code=404, detail="Recipient user not found")
            recipient_id, recipient_public_key = recipient

            cur.execute("SELECT email FROM users WHERE id = %s", (owner_id,))
            owner_row = cur.fetchone()
            if not owner_row:
                raise HTTPException(status_code=404, detail="Owner not found")
            owner_email = owner_row[0]


        env_key_prefix = f"USER_{owner_email.upper().replace('@', '_').replace('.', '_')}"
        owner_encrypted_private_key = os.getenv(f"{env_key_prefix}_ENCRYPTED_PRIVATE_KEY")
        owner_aes_key_hex = os.getenv(f"{env_key_prefix}_AES_KEY")
        if not owner_encrypted_private_key or not owner_aes_key_hex:
            raise HTTPException(status_code=404, detail="Owner encrypted key not found in environment")
        owner_aes_key = bytes.fromhex(owner_aes_key_hex)
        owner_private_key = decrypt_private_key(owner_encrypted_private_key, owner_aes_key)

        original_aes_key_hex = decrypt_rsa(owner_private_key, int(encrypted_aes_key))
        encrypted_aes_key_for_recipient = encrypt_rsa(recipient_public_key, original_aes_key_hex)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO shared_files (file_id, shared_with, encrypted_aes_key, permission)
                VALUES (%s, %s, %s, %s)
                """,
                (file_id, recipient_id, encrypted_aes_key_for_recipient, permission),
            )
            conn.commit()

        return {"message": "File shared successfully"}

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shared-files")
async def get_shared_files(authorization: str = Header(...)):
    try:

        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)
        if not decoded_token:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        user_id = decoded_token["user_id"]

        with conn.cursor() as cursor:
            cursor.execute("SELECT email FROM users WHERE id = %s", (user_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            user_email = row[0]
        
        env_key_prefix = f"USER_{user_email.upper().replace('@', '_').replace('.', '_')}"
        encrypted_private_key = os.getenv(f"{env_key_prefix}_ENCRYPTED_PRIVATE_KEY")
        aes_key_hex = os.getenv(f"{env_key_prefix}_AES_KEY")
        if not encrypted_private_key or not aes_key_hex:
            raise HTTPException(status_code=404, detail="Encrypted key not found in environment")
        recipient_aes_key = bytes.fromhex(aes_key_hex)
        private_key = decrypt_private_key(encrypted_private_key, recipient_aes_key)

        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT f.file_name, f.file_type, f.file_url, sf.encrypted_aes_key, u.email AS owner_email, sf.permission
                FROM shared_files sf
                JOIN files f ON sf.file_id = f.id
                JOIN users u ON f.owner_id = u.id
                WHERE sf.shared_with = %s
            """, (user_id,))
            shared_files = cursor.fetchall()

        decrypted_files = []
        for record in shared_files:
            file_name, file_type, file_url, shared_encrypted_aes_key, owner_email, permission = record

            try:
                aes_key_hex_decrypted = decrypt_rsa(private_key, int(shared_encrypted_aes_key))
            except Exception as e:
                decrypted_files.append({
                    "file_name": file_name,
                    "owner_email": owner_email,
                    "permission": permission,
                    "error": f"Failed to decrypt AES key: {str(e)}"
                })
                continue

            file_aes_key = bytes.fromhex(aes_key_hex_decrypted)

            encrypted_file_response = requests.get(file_url)
            if encrypted_file_response.status_code != 200:
                decrypted_files.append({
                    "file_name": file_name,
                    "owner_email": owner_email,
                    "permission": permission,
                    "error": "Failed to download encrypted file"
                })
                continue

            encrypted_file_content = encrypted_file_response.content

            iv = encrypted_file_content[:16]
            ciphertext = encrypted_file_content[16:]

            cipher = AES.new(file_aes_key, AES.MODE_CBC, iv)
            try:
                decrypted_content = unpad(cipher.decrypt(ciphertext), BLOCK_SIZE)
            except Exception as e:
                decrypted_files.append({
                    "file_name": file_name,
                    "owner_email": owner_email,
                    "permission": permission,
                    "error": f"Error during file decryption: {str(e)}"
                })
                continue

            if file_type.startswith("text/"):
                content = decrypted_content.decode("utf-8", errors="ignore")
            else:
                content = base64.b64encode(decrypted_content).decode("utf-8")

            decrypted_files.append({
                "file_name": file_name,
                "file_type": file_type,
                "owner_email": owner_email,
                "permission": permission,
                "decrypted_content": content
            })

        return {
            "message": "Shared files retrieved and decrypted successfully",
            "shared_files": decrypted_files
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))