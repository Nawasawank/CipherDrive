import os
from Cryptodome.Cipher import AES
from Cryptodome.Protocol.KDF import PBKDF2
from Cryptodome.Random import get_random_bytes
from Cryptodome.Util.Padding import pad, unpad

# Constants
BLOCK_SIZE = AES.block_size  # 16 bytes
KEY_SIZE = 32  # 32 bytes for AES-256
PBKDF2_ITERATIONS = 100000

def derive_key(password: str, salt: bytes) -> bytes:
    return PBKDF2(password.encode(), salt, dkLen=KEY_SIZE, count=PBKDF2_ITERATIONS)

def encrypt_private_key(private_key: str, password: str) -> str:
    salt = get_random_bytes(16)
    iv = get_random_bytes(16)
    key = derive_key(password, salt)

    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_private_key = pad(private_key.encode(), BLOCK_SIZE)
    ciphertext = cipher.encrypt(padded_private_key)
    return (salt + iv + ciphertext).hex()

def decrypt_private_key(encrypted_private_key_hex: str, password: str) -> str:
    encrypted_private_key = bytes.fromhex(encrypted_private_key_hex)
    salt = encrypted_private_key[:16]
    iv = encrypted_private_key[16:32]
    ciphertext = encrypted_private_key[32:]
    key = derive_key(password, salt)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_private_key = cipher.decrypt(ciphertext)
    private_key = unpad(padded_private_key, BLOCK_SIZE)
    return private_key.decode()

def generate_aes_key() -> str:
    """Generates a random AES key and returns it as a hex string."""
    aes_key = get_random_bytes(KEY_SIZE)
    return aes_key.hex()

# (The rest of your file encryption/decryption functions remain unchanged.)
