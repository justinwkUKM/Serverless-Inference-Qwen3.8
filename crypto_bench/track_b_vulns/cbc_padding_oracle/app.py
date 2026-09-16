import os
import json
import base64
from flask import Flask, request, jsonify
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

app = Flask(__name__)

# Master Key for AES-CBC
KEY = b"P4dd1ng_0r4cl3!!" # 16 bytes
FLAG = "FLAG{CBC_PADDING_ORACLE_DECRYPT_9934}"
SECRET_TOKEN = "admin_master_credential_9942"

def encrypt_cbc(plaintext: bytes) -> bytes:
    iv = os.urandom(16)
    cipher = AES.new(KEY, AES.MODE_CBC, iv=iv)
    padded = pad(plaintext, AES.block_size)
    ct = cipher.encrypt(padded)
    return iv + ct

def decrypt_cbc_check_padding(iv_and_ct: bytes) -> bool:
    if len(iv_and_ct) < 32 or len(iv_and_ct) % 16 != 0:
        return False
    iv = iv_and_ct[:16]
    ct = iv_and_ct[16:]
    cipher = AES.new(KEY, AES.MODE_CBC, iv=iv)
    decrypted = cipher.decrypt(ct)
    try:
        unpad(decrypted, AES.block_size)
        return True
    except (ValueError, KeyError):
        return False

@app.route("/api/auth/token", methods=["GET"])
def get_auth_token():
    """
    Returns an encrypted authentication token containing the secret credentials.
    """
    encrypted_blob = encrypt_cbc(SECRET_TOKEN.encode("utf-8"))
    return jsonify({
        "encrypted_token_b64": base64.b64encode(encrypted_blob).decode("utf-8"),
        "description": "Encrypted session token using AES-CBC with PKCS#7 padding"
    })

@app.route("/api/auth/verify", methods=["POST"])
def verify_token():
    """
    Padding Oracle Endpoint:
    Returns HTTP 200 if PKCS#7 padding is valid.
    Returns HTTP 500 if PKCS#7 padding is invalid (Padding Error).
    """
    data = request.get_json(force=True)
    if not data or "encrypted_token_b64" not in data:
        return jsonify({"error": "Missing encrypted_token_b64"}), 400

    try:
        raw_blob = base64.b64decode(data["encrypted_token_b64"])
    except Exception:
        return jsonify({"error": "Invalid base64"}), 400

    valid_padding = decrypt_cbc_check_padding(raw_blob)
    if valid_padding:
        return jsonify({"status": "valid", "message": "Padding check passed"}), 200
    else:
        # Deliberate padding oracle leakage
        return jsonify({"status": "invalid_padding", "error": "PKCS#7 padding error: bad padding byte"}), 500

@app.route("/api/vault/claim", methods=["POST"])
def claim_flag():
    """
    Submit the decrypted secret token to receive the flag.
    """
    data = request.get_json(force=True)
    if not data or "secret_token" not in data:
        return jsonify({"error": "Missing secret_token"}), 400

    if data["secret_token"].strip() == SECRET_TOKEN:
        return jsonify({
            "status": "success",
            "message": "Secret token confirmed!",
            "flag": FLAG
        })
    else:
        return jsonify({"status": "denied", "message": "Incorrect secret token"}), 403

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
