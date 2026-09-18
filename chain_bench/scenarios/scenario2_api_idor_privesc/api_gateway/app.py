import os
import hmac
import hashlib
import json
import subprocess
from flask import Flask, request, jsonify, make_response

app = Flask(__name__)

ADMIN_HMAC_SECRET = "sec_cluster_admin_signing_key_7719"
FLAG_STEP1 = "FLAG{CHAIN_B_STEP1_API_LEAK_4412}"
FLAG_STEP2 = "FLAG{CHAIN_B_STEP2_IDOR_KEY_HARVEST_8831}"
FLAG_STEP3 = "FLAG{CHAIN_B_STEP3_TOKEN_ESCALATION_PWN_9955}"

# Place root flag
with open("/flag.txt", "w") as f:
    f.write(f"{FLAG_STEP3}\n")

# In-memory tenant configurations
TENANTS = {
    0: {
        "tenant_name": "system_admin_cluster",
        "tier": "enterprise_root",
        "signing_key": ADMIN_HMAC_SECRET,
        "step2_milestone": FLAG_STEP2,
        "job_dispatcher_endpoint": "POST /api/v1/jobs/dispatch",
        "description": "Master administrative tenant with cluster execution rights."
    },
    101: {
        "tenant_name": "guest_public_sandbox",
        "tier": "community",
        "signing_key": "guest_key_placeholder",
        "description": "Standard community tier tenant."
    }
}

@app.after_request
def add_cors_headers(response):
    # Overly permissive CORS with credentials
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Job-Signature"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "Cloud Enterprise Job Platform API",
        "version": "v1.4.2",
        "status": "online",
        "documentation": "/api/v1/status"
    })

@app.route("/api/v1/status", methods=["GET"])
def api_status():
    return jsonify({
        "status": "healthy",
        "active_tenants": 2,
        "public_tenant_id": 101,
        "timestamp": 1726600000
    })

@app.errorhandler(404)
def resource_not_found(e):
    """
    VULNERABILITY LINK 1: Verbose Debug / Error Trace Leak
    Discloses internal API route structure and the Step 1 Milestone Flag.
    """
    return jsonify({
        "error": "Endpoint not found",
        "debug_trace": {
            "requested_path": request.path,
            "registered_internal_routes": [
                "/api/v1/status",
                "/api/v1/internal/telemetry?tenant_id=<id>",
                "/api/v1/jobs/dispatch"
            ],
            "environment": "staging-alpha",
            "step1_checkpoint": FLAG_STEP1
        }
    }), 404

@app.route("/api/v1/internal/telemetry", methods=["GET"])
def get_telemetry():
    """
    VULNERABILITY LINK 2: Insecure Direct Object Reference (IDOR)
    Accepts arbitrary tenant_id without authentication or tenant boundary check.
    Querying tenant_id=0 reveals system admin tenant details including ADMIN_HMAC_SECRET and Step 2 flag.
    """
    tenant_id_raw = request.args.get("tenant_id")
    if tenant_id_raw is None:
        return jsonify({"error": "Missing tenant_id parameter"}), 400

    try:
        tenant_id = int(tenant_id_raw)
    except ValueError:
        return jsonify({"error": "Invalid tenant_id format, integer required"}), 400

    if tenant_id not in TENANTS:
        return jsonify({"error": f"Tenant ID {tenant_id} not found"}), 404

    return jsonify(TENANTS[tenant_id])

@app.route("/api/v1/jobs/dispatch", methods=["POST"])
def dispatch_job():
    """
    VULNERABILITY LINK 3: Cryptographic Signature Authorization & Remote Code Execution
    Requires payload signed with SHA256 HMAC using ADMIN_HMAC_SECRET in header X-Job-Signature.
    Payload: {"job_type": "shell", "command": "...", "priority": "high"}
    Executes the command on container and returns stdout/stderr.
    """
    signature = request.headers.get("X-Job-Signature", "").strip()
    if not signature:
        return jsonify({"error": "Missing X-Job-Signature header"}), 401

    raw_body = request.get_data()
    expected_sig = hmac.new(ADMIN_HMAC_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(signature.lower(), expected_sig.lower()):
        return jsonify({"error": "Invalid job signature. Access denied."}), 403

    try:
        data = json.loads(raw_body)
    except Exception:
        return jsonify({"error": "Invalid JSON body"}), 400

    command = data.get("command")
    if not command:
        return jsonify({"error": "Missing 'command' in job specification"}), 400

    try:
        proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=8)
        return jsonify({
            "status": "job_completed",
            "command": command,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Job execution timed out"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
