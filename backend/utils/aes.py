import os
from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes
from Cryptodome.Util.Padding import pad, unpad

# Constants
BLOCK_SIZE = AES.block_size  # 16 bytes
KEY_SIZE = 32  # 32 bytes for AES-256

def generate_aes_key() -> bytes:
    return get_random_bytes(KEY_SIZE)

def encrypt_private_key(private_key: str, aes_key: bytes) -> str:
    iv = get_random_bytes(16)
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    padded_private_key = pad(private_key.encode(), BLOCK_SIZE)
    ciphertext = cipher.encrypt(padded_private_key)
    return (iv + ciphertext).hex()

def decrypt_private_key(encrypted_private_key_hex: str, aes_key: bytes) -> str:
    encrypted_private_key = bytes.fromhex(encrypted_private_key_hex)
    iv = encrypted_private_key[:16]
    ciphertext = encrypted_private_key[16:]
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    padded_private_key = cipher.decrypt(ciphertext)
    private_key = unpad(padded_private_key, BLOCK_SIZE)
    return private_key.decode()