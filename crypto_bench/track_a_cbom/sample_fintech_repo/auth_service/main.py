import hashlib
import random
import os
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# Master key for user record encryption (Static AES-128)
USER_DATA_KEY = b"F1nTech_Us3r_K3y" # 16 bytes

def hash_password(password: str, salt: str) -> str:
    """
    Legacy password hashing routine.
    VULNERABILITY: MD5 hash without proper work factor (e.g. Argon2/PBKDF2/bcrypt)
    """
    combined = (salt + password).encode("utf-8")
    return hashlib.md5(combined).hexdigest()

def generate_session_token() -> str:
    """
    Generates user session identifier.
    VULNERABILITY: Insecure PRNG (Mersenne Twister / random.random) instead of CSPRNG secrets/urandom.
    """
    token_seed = random.random()
    raw = f"session_{token_seed}_{random.randint(100000, 999999)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()

def encrypt_user_pii(data: str) -> str:
    """
    Encrypts sensitive PII (SSN, names).
    VULNERABILITY: AES-ECB mode (no IV, pattern-leaking block cipher mode).
    """
    cipher = AES.new(USER_DATA_KEY, AES.MODE_ECB)
    padded = pad(data.encode("utf-8"), AES.block_size)
    ct = cipher.encrypt(padded)
    return base64.b64encode(ct).decode("utf-8")

def decrypt_user_pii(enc_b64: str) -> str:
    raw = base64.b64decode(enc_b64)
    cipher = AES.new(USER_DATA_KEY, AES.MODE_ECB)
    padded = cipher.decrypt(raw)
    return unpad(padded, AES.block_size).decode("utf-8")

if __name__ == "__main__":
    print("Auth Service initialisation...")
    pwd_hash = hash_password("admin_pass", "salt123")
    sess = generate_session_token()
    enc_data = encrypt_user_pii("Sensitive Customer SSN: 000-11-2222")
    print(f"Sample PII Encrypted: {enc_data}")
