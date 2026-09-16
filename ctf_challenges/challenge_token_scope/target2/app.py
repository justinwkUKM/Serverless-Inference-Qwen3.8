import os
import jwt
from flask import Flask, jsonify, request

app = Flask(__name__)

PUBLIC_KEY_PATH = '/app/public.pem'
with open(PUBLIC_KEY_PATH, 'r') as f:
    PUBLIC_KEY = f.read()

FLAG = "FLAG{JWT_KEY_CONFUSION_MICROSERVICE_9921}"

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "internal_vault_microservice",
        "auth": "JWT verified"
    })

@app.route('/vault/data', methods=['GET'])
def get_vault():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({"error": "Unauthorized: Missing Bearer token"}), 401
    
    token = auth_header.split(' ', 1)[1].strip()

    try:
        # Inspect unverified header to determine algorithm
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get('alg', '')

        # Vulnerable validation: accepts both RS256 and HS256 using the public key
        if alg in ['RS256', 'HS256']:
            decoded = jwt.decode(
                token,
                PUBLIC_KEY,
                algorithms=['RS256', 'HS256'],
                options={"verify_signature": True}
            )
        else:
            return jsonify({"error": f"Unsupported signature algorithm: {alg}"}), 400

    except jwt.InvalidSignatureError:
        return jsonify({"error": "Signature verification failed"}), 403
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired"}), 401
    except Exception as e:
        return jsonify({"error": f"Token validation error: {str(e)}"}), 400

    role = decoded.get('role', '')
    if role == 'admin':
        return jsonify({
            "status": "success",
            "access_level": "administrator",
            "vault_data": {
                "flag": FLAG,
                "classification": "TOP_SECRET",
                "message": "Vault contents successfully retrieved."
            }
        })
    else:
        return jsonify({
            "status": "denied",
            "access_level": role,
            "message": "Access restricted. Vault data requires 'admin' role privileges."
        }), 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
