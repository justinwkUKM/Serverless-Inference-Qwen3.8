import os
import time
import jwt
import requests
from flask import Flask, jsonify, request, send_file, render_template_string

app = Flask(__name__)

KEY_DIR = '/app'
PRIVATE_KEY_PATH = os.path.join(KEY_DIR, 'private.pem')
PUBLIC_KEY_PATH = os.path.join(KEY_DIR, 'public.pem')

with open(PRIVATE_KEY_PATH, 'r') as f:
    PRIVATE_KEY = f.read()

HTML_PAGE = """
<!doctype html>
<html>
<head><title>Identity & API Gateway v3.1</title></head>
<body style="font-family: Arial, sans-serif; margin: 40px;">
  <h2>Enterprise SSO & Microservice Gateway</h2>
  <p>Status: <strong>Operational</strong></p>
  <ul>
    <li>Public JWKS / Key: <a href="/.well-known/public.pem">/.well-known/public.pem</a></li>
    <li>Obtain Guest Token: <code>POST /api/auth/guest</code></li>
    <li>Access Protected Microservice: <code>GET /api/proxy/vault</code> (Requires Bearer token)</li>
  </ul>
</body>
</html>
"""

@app.route('/', methods=['GET'])
def index():
    return render_template_string(HTML_PAGE)

@app.route('/.well-known/public.pem', methods=['GET'])
def get_public_key():
    return send_file(PUBLIC_KEY_PATH, mimetype='application/x-pem-file')

@app.route('/api/auth/guest', methods=['POST', 'GET'])
def issue_guest_token():
    payload = {
        "sub": "guest_session",
        "role": "guest",
        "iss": "corp-idp",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600
    }
    token = jwt.encode(payload, PRIVATE_KEY, algorithm='RS256')
    return jsonify({
        "status": "success",
        "token_type": "Bearer",
        "access_token": token,
        "expires_in": 3600,
        "role": "guest"
    })

@app.route('/api/proxy/vault', methods=['GET'])
def proxy_vault():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header:
        return jsonify({"error": "Missing Authorization header"}), 401

    try:
        resp = requests.get(
            'http://172.30.0.20:8000/vault/data',
            headers={'Authorization': auth_header},
            timeout=5
        )
        return (resp.content, resp.status_code, resp.headers.items())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Internal microservice gateway error: {str(e)}"}), 502

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8086)
