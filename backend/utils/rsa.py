import random

first_primes_list = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29,
					31, 37, 41, 43, 47, 53, 59, 61, 67,
					71, 73, 79, 83, 89, 97, 101, 103,
					107, 109, 113, 127, 131, 137, 139,
					149, 151, 157, 163, 167, 173, 179,
					181, 191, 193, 197, 199, 211, 223,
					227, 229, 233, 239, 241, 251, 257,
					263, 269, 271, 277, 281, 283, 293,
					307, 311, 313, 317, 331, 337, 347, 349]

def nBitRandom(n):
    return random.randrange(2**(n - 1) + 1, 2**n - 1)

def getLowLevelPrime(n):
    while True:
        pc = nBitRandom(n)
        for divisor in first_primes_list:
            if pc % divisor == 0 and divisor**2 <= pc:
                break
        else:
            return pc

def isMillerRabinPassed(mrc):
    maxDivByTwo = 0
    ec = mrc - 1
    while ec % 2 == 0:
        ec //= 2
        maxDivByTwo += 1
    assert (2 ** maxDivByTwo * ec == mrc - 1)

    for _ in range(20): 
        tester = random.randrange(2, mrc)
        if pow(tester, ec, mrc) == 1:
            continue
        for i in range(maxDivByTwo):
            if pow(tester, 2 ** i * ec, mrc) == mrc - 1:
                break
        else:
            return False
    return True

def generatePrime(n):
    while True:
        candidate = getLowLevelPrime(n)
        if isMillerRabinPassed(candidate):
            return candidate

def moduloExp(a, m, n):
    binary = bin(m)[2:]
    d = 1
    for bit in binary:
        d = (d * d) % n
        if bit == '1':
            d = (d * a) % n
    return d


def EuclidGCD(a, b):
    while b != 0:
        a, b = b, a % b
    return a

def mulInverse(a, m):
    m0, x0, x1 = m, 0, 1
    while a > 1:
        q = a // m
        a, m = m, a % m
        x0, x1 = x1 - q * x0, x0
    if x1 < 0:
        x1 += m0
    return x1

def generate_rsa_keys(bits=512):
    p = generatePrime(bits // 2)
    q = generatePrime(bits // 2)
    while p == q:
        q = generatePrime(bits // 2)

    n = p * q
    phi = (p - 1) * (q - 1)

    while True:
        e = random.randrange(2, phi)
        if EuclidGCD(e, phi) == 1:
            break

    d = mulInverse(e, phi)

    public_key = f"{e},{n}"
    private_key = f"{d},{n}"
    return public_key, private_key

def encrypt_rsa(public_key, plaintext):
    e, n = map(int, public_key.split(","))
    plaintext_bytes = plaintext.encode('utf-8')
    plaintext_int = int.from_bytes(plaintext_bytes, byteorder='big')
    ciphertext = moduloExp(plaintext_int, e, n)
    return ciphertext

def decrypt_rsa(private_key, ciphertext):
    d, n = map(int, private_key.split(","))
    plaintext_int = moduloExp(ciphertext, d, n)
    plaintext_bytes = plaintext_int.to_bytes((plaintext_int.bit_length() + 7) // 8, byteorder='big')
    return plaintext_bytes.decode('utf-8', errors='ignore')