import os
from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes

KEY_SIZE = 32 

def generate_aes_key() -> bytes:
    return get_random_bytes(KEY_SIZE)

def encrypt_private_key(private_key: str, aes_key: bytes) -> str:
    cipher = AES.new(aes_key, AES.MODE_EAX)
    nonce = cipher.nonce
    ciphertext, tag = cipher.encrypt_and_digest(private_key.encode())

    return (nonce + tag + ciphertext).hex()

def decrypt_private_key(encrypted_private_key_hex: str, aes_key: bytes) -> str:
    encrypted_data = bytes.fromhex(encrypted_private_key_hex)

    nonce = encrypted_data[:16]
    tag = encrypted_data[16:32]
    ciphertext = encrypted_data[32:]

    cipher = AES.new(aes_key, AES.MODE_EAX, nonce=nonce)
    decrypted = cipher.decrypt_and_verify(ciphertext, tag)

    return decrypted.decode()
