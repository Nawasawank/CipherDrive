from Cryptodome.Util import number
import random

def generate_rsa_keys(bits=2048):
    
    p = number.getPrime(bits // 2)
    q = number.getPrime(bits // 2)
    while p == q:
        q = number.getPrime(bits // 2)
        
    n = p * q
    phi = (p - 1) * (q - 1)
    
    e = random.randrange(1, phi)
    while number.GCD(e, phi) != 1:
        e = random.randrange(1, phi)
    
    d = number.inverse(e, phi)
    
    public_key = f"{e},{n}"
    private_key = f"{d},{n}"
    return public_key, private_key

def encrypt_rsa(public_key, plaintext):
    e, n = map(int, public_key.split(","))
    plaintext_bytes = plaintext.encode('utf-8')
    plaintext_int = int.from_bytes(plaintext_bytes, byteorder='big')
    ciphertext = pow(plaintext_int, e, n)
    return ciphertext

def decrypt_rsa(private_key, ciphertext):
    d, n = map(int, private_key.split(","))
    plaintext_int = pow(ciphertext, d, n)
    plaintext_bytes = plaintext_int.to_bytes((plaintext_int.bit_length() + 7) // 8, byteorder='big')
    plaintext = plaintext_bytes.decode('utf-8', errors='ignore')
    return plaintext
