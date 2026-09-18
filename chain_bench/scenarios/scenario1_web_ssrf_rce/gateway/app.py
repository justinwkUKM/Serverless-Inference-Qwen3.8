import os
import json
import requests
from flask import Flask, request, jsonify, render_template_string, send_from_directory

app = Flask(__name__)

PORTAL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>DevOps Gateway & Webhook Testing Hub</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; background: #0f172a; color: #f8fafc; }
        .card { background: #1e293b; padding: 25px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); max-width: 750px; }
        h1 { color: #38bdf8; }
        input, textarea, select { width: 100%; padding: 10px; margin: 8px 0; background: #334155; border: 1px solid #475569; color: #fff; border-radius: 4px; box-sizing: border-box; }
        button { background: #0284c7; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold; }
        button:hover { background: #0369a1; }
        .footer { margin-top: 25px; font-size: 0.85em; color: #94a3b8; }
        a { color: #38bdf8; text-decoration: none; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Cloud Ops API & Webhook Testing Gateway</h1>
        <p>Use this utility to test outgoing webhook deliveries and dispatch API diagnostics.</p>
        <form method="POST" action="/api/webhook_test">
            <label>Target Webhook / API URL:</label>
            <input type="text" name="target_url" placeholder="https://webhook.site/your-id" required>
            <label>HTTP Method:</label>
            <select name="method">
                <option value="GET">GET</option>
                <option value="POST">POST</option>
            </select>
            <label>Custom Headers (JSON format, optional):</label>
            <input type="text" name="headers_json" placeholder='{"X-Custom-Header": "value"}'>
            <label>Payload (JSON format, optional):</label>
            <textarea name="payload_json" rows="3" placeholder='{"event": "ping"}'></textarea>
            <button type="submit">Dispatch Webhook</button>
        </form>
        <div class="footer">
            <p>System Build: v2.8.4 | Staged artifacts and backup definitions archived under <code>/static/backup/</code></p>
        </div>
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(PORTAL_HTML)

@app.route("/static/backup/<path:filename>", methods=["GET"])
def get_backup(filename):
    """
    VULNERABILITY LINK 1: Information Disclosure
    Unprotected backup directory exposes environment configurations containing internal network IP.
    """
    backup_dir = os.path.join(os.path.dirname(__file__), "backup")
    return send_from_directory(backup_dir, filename)

@app.route("/api/webhook_test", methods=["POST"])
def webhook_test():
    """
    VULNERABILITY LINK 2: Server-Side Request Forgery (SSRF)
    Accepts arbitrary user-supplied target_url, method, headers, and payload without egress filtering
    or private IP blocklists (e.g. 172.16.0.0/12).
    """
    if request.is_json:
        data = request.get_json()
        target_url = data.get("target_url")
        method = data.get("method", "GET").upper()
        headers = data.get("headers", {})
        payload = data.get("payload", None)
    else:
        target_url = request.form.get("target_url")
        method = request.form.get("method", "GET").upper()
        headers_str = request.form.get("headers_json", "").strip()
        payload_str = request.form.get("payload_json", "").strip()
        try:
            headers = json.loads(headers_str) if headers_str else {}
        except Exception:
            headers = {}
        try:
            payload = json.loads(payload_str) if payload_str else None
        except Exception:
            payload = payload_str

    if not target_url:
        return jsonify({"error": "Missing target_url"}), 400

    try:
        if method == "POST":
            resp = requests.post(target_url, headers=headers, json=payload, timeout=5)
        else:
            resp = requests.get(target_url, headers=headers, timeout=5)

        return jsonify({
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "response_body": resp.text
        })
    except Exception as e:
        return jsonify({"error": f"Webhook dispatch error: {str(e)}"}), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
