import os
import subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)

INTERNAL_SECRET_KEY = "diag_sec_token_9918"
STEP2_FLAG = "FLAG{CHAIN_STEP2_SSRF_PIVOT_7742}"
STEP3_FLAG = "FLAG{CHAIN_STEP3_RCE_SYSTEM_TAKEOVER_9918}"

# Ensure root flag file exists
with open("/flag.txt", "w") as f:
    f.write(f"{STEP3_FLAG}\n")

@app.route("/internal/health", methods=["GET"])
def internal_health():
    """
    VULNERABILITY LINK 2 TARGET:
    Reachable only via internal network (or SSRF).
    Leaks diagnostic token and Step 2 flag.
    """
    return jsonify({
        "status": "healthy",
        "service": "cluster_task_daemon",
        "step2_milestone": STEP2_FLAG,
        "diagnostic_auth": {
            "header_name": "X-Internal-Key",
            "required_token": INTERNAL_SECRET_KEY,
            "diagnostic_endpoint": "POST /api/v1/run_diagnostic",
            "accepted_parameters": {"check_host": "IP address or hostname to ping"}
        }
    })

@app.route("/api/v1/run_diagnostic", methods=["POST"])
def run_diagnostic():
    """
    VULNERABILITY LINK 3 TARGET:
    Requires X-Internal-Key header.
    Executes ping diagnostic with unsanitized command parameter check_host (Command Injection).
    """
    auth_header = request.headers.get("X-Internal-Key")
    if not auth_header or auth_header != INTERNAL_SECRET_KEY:
        return jsonify({"error": "Unauthorized: Invalid or missing X-Internal-Key"}), 401

    data = request.get_json(silent=True) or request.form or request.args
    check_host = data.get("check_host") if hasattr(data, "get") else None
    if not check_host:
        return jsonify({"error": "Missing check_host parameter"}), 400

    # Command Injection Vulnerability
    # The host is passed directly into a shell string
    cmd = f"ping -c 1 {check_host}"
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=8
        )
        output = proc.stdout + proc.stderr
        return jsonify({
            "command_executed": cmd,
            "returncode": proc.returncode,
            "output": output
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Diagnostic execution timed out"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
