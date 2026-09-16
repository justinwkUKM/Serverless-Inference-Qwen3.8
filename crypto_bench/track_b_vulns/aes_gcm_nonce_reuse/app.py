import os
import json
import base64
from flask import Flask, request, jsonify
from Crypto.Cipher import AES

app = Flask(__name__)

# Master 128-bit key and STATIC 12-byte Nonce
# VULNERABILITY: Static nonce reuse across multiple GCM encryptions
KEY = b"Crypt0B3nch_K3y!" # 16 bytes
REUSED_NONCE = b"ST4T1C_N0NCE" # 12 bytes
FLAG = "FLAG{AES_GCM_NONCE_REUSE_FORGERY_8819}"

def gcm_encrypt(plaintext: bytes, nonce: bytes) -> tuple:
    cipher = AES.new(KEY, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    return ciphertext, tag

def gcm_decrypt(ciphertext: bytes, nonce: bytes, tag: bytes) -> bytes:
    cipher = AES.new(KEY, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)

@app.route("/api/sample", methods=["GET"])
def get_sample():
    """
    Returns standard system sample ciphertexts encrypted with the reused nonce.
    """
    sample_text = request.args.get("msg", "action=view_balance&role=user&timestamp=1726000000").encode("utf-8")
    ct, tag = gcm_encrypt(sample_text, REUSED_NONCE)
    return jsonify({
        "nonce_hex": REUSED_NONCE.hex(),
        "ciphertext_hex": ct.hex(),
        "tag_hex": tag.hex(),
        "message": sample_text.decode("utf-8")
    })

@app.route("/api/execute", methods=["POST"])
def execute_command():
    """
    Accepts an encrypted transaction token.
    If the tag is valid and decrypted message contains 'role=admin', releases the flag.
    """
    data = request.get_json(force=True)
    if not data or "ciphertext_hex" not in data or "tag_hex" not in data:
        return jsonify({"error": "Missing ciphertext_hex or tag_hex"}), 400

    try:
        ct = bytes.fromhex(data["ciphertext_hex"])
        tag = bytes.fromhex(data["tag_hex"])
        pt = gcm_decrypt(ct, REUSED_NONCE, tag)
        message = pt.decode("utf-8", errors="ignore")

        if "role=admin" in message:
            return jsonify({
                "status": "success",
                "message": "Privilege verified! Vault unlocked.",
                "flag": FLAG
            })
        else:
            return jsonify({
                "status": "denied",
                "message": f"Execution permitted for standard user: {message}"
            })
    except ValueError:
        return jsonify({"status": "error", "message": "Authentication tag verification failed!"}), 403
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
