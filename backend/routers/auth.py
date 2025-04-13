from fastapi import APIRouter, HTTPException
from schemas.auth import RegisterRequest, LoginRequest
from db import cursor, conn
from utils.jwt_handler import create_access_token
from utils.rsa import generate_rsa_keys
from utils.aes import encrypt_private_key, generate_aes_key
import bcrypt
from dotenv import load_dotenv, set_key  # Requires python-dotenv
import os

router = APIRouter()

env_file = ".env"
load_dotenv(dotenv_path=env_file)

@router.post("/register")
def register(data: RegisterRequest):
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (data.email,))
        existing_user = cursor.fetchone()
        if existing_user:
            raise HTTPException(status_code=409, detail="Email already registered")

        hashed_pw = bcrypt.hashpw(data.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        public_key, private_key = generate_rsa_keys(bits=2048)
        print(f"Generated RSA keys: {public_key}, {private_key}")
        encrypted_private_key = encrypt_private_key(private_key, data.password)


        aes_key = generate_aes_key()
        print(f"Generated AES key: {aes_key}")

        user_key_prefix = f"USER_{data.email.upper().replace('@', '_').replace('.', '_')}"

        set_key(env_file, f"{user_key_prefix}_ENCRYPTED_PRIVATE_KEY", encrypted_private_key)
        set_key(env_file, f"{user_key_prefix}_AES_KEY", aes_key)

        cursor.execute(
            "INSERT INTO users (email, password, rsa_public_key) VALUES (%s, %s, %s)",
            (data.email, hashed_pw, public_key)
        )
        conn.commit()

        return {
            "message": "User registered successfully",
            "env_keys": {
                f"{user_key_prefix}_ENCRYPTED_PRIVATE_KEY": encrypted_private_key,
                f"{user_key_prefix}_AES_KEY": aes_key
            }
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
def login(data: LoginRequest):
    try:
        cursor.execute("SELECT id, email, password, role FROM users WHERE email = %s", (data.email,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        db_id, db_email, db_hashed_password, db_role = user
        if not bcrypt.checkpw(data.password.encode("utf-8"), db_hashed_password.encode("utf-8")):
            raise HTTPException(status_code=401, detail="Incorrect password")

        token = create_access_token({
            "user_id": db_id,
            "role": db_role
        })
        return {
            "message": "Login successful",
            "access_token": token
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
