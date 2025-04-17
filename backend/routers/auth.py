from fastapi import APIRouter, HTTPException, Header
from schemas.auth import RegisterRequest, LoginRequest
from db import get_db  
from utils.jwt_handler import create_access_token, verify_token
from utils.rsa import generate_rsa_keys
from utils.aes import encrypt_private_key, generate_aes_key
import bcrypt
from dotenv import load_dotenv, set_key
import os

router = APIRouter()

env_file = ".env"
load_dotenv(dotenv_path=env_file)

@router.post("/register")
def register(data: RegisterRequest):
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE email = %s", (data.email,))
                existing_user = cursor.fetchone()
                if existing_user:
                    raise HTTPException(status_code=409, detail="Email already registered")

                hashed_pw = bcrypt.hashpw(data.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

                public_key, private_key = generate_rsa_keys(bits=2048)
                aes_key = generate_aes_key()
                encrypted_private_key = encrypt_private_key(private_key, aes_key)

                user_key_prefix = f"USER_{data.email.upper().replace('@', '_').replace('.', '_')}"
                set_key(env_file, f"{user_key_prefix}_ENCRYPTED_PRIVATE_KEY", encrypted_private_key)
                set_key(env_file, f"{user_key_prefix}_AES_KEY", aes_key.hex())

                cursor.execute(
                    "INSERT INTO users (email, password, rsa_public_key) VALUES (%s, %s, %s)",
                    (data.email, hashed_pw, public_key)
                )
                conn.commit()

        return {
            "message": "User registered successfully",
            "env_keys": {
                f"{user_key_prefix}_ENCRYPTED_PRIVATE_KEY": encrypted_private_key,
                f"{user_key_prefix}_AES_KEY": aes_key.hex()
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/login")
def login(data: LoginRequest):
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, email, password, role, is_locked 
                    FROM users 
                    WHERE email = %s
                """, (data.email,))
                user = cursor.fetchone()

                if not user:
                    cursor.execute(
                        "INSERT INTO user_activity_log (user_id, action, metadata) VALUES (%s, %s, %s)",
                        (None, 'failed_login', data.email)
                    )
                    conn.commit()
                    raise HTTPException(status_code=401, detail="Invalid credentials")

                db_id, db_email, db_hashed_password, db_role, is_locked = user

                if is_locked:
                    raise HTTPException(status_code=403, detail="Your account is locked")

                if not bcrypt.checkpw(data.password.encode(), db_hashed_password.encode()):
                    cursor.execute(
                        "INSERT INTO user_activity_log (user_id, action, metadata) VALUES (%s, %s, %s)",
                        (db_id, 'failed_login', data.email)
                    )
                    conn.commit()
                    raise HTTPException(status_code=401, detail="Invalid credentials")

                cursor.execute(
                    "INSERT INTO user_activity_log (user_id, action, metadata) VALUES (%s, %s, %s)",
                    (db_id, 'login', data.email)
                )
                conn.commit()

        token = create_access_token({
            "user_id": db_id,
            "role": db_role
        })

        return {
            "message": "Login successful",
            "access_token": token,
            "role": db_role
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/user-details")
def get_user_details(authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        decoded_token = verify_token(token)

        if not decoded_token:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        user_id = decoded_token["user_id"]

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT email FROM users WHERE id = %s", (user_id,)
                )
                user = cursor.fetchone()
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")

                return {
                    "email": user[0]
                }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))