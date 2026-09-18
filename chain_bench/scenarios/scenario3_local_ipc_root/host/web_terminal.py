import os
import subprocess
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

HTML_UI = """
<!DOCTYPE html>
<html>
<head>
    <title>Server Maintenance Terminal Console</title>
    <style>
        body { background-color: #121824; color: #e2e8f0; font-family: monospace; margin: 30px; }
        .box { background-color: #1e293b; border: 1px solid #334155; padding: 20px; border-radius: 6px; max-width: 800px; }
        input[type=text] { width: 80%; padding: 8px; background: #0f172a; border: 1px solid #475569; color: #38bdf8; font-family: monospace; }
        button { padding: 8px 16px; background: #2563eb; color: white; border: none; cursor: pointer; border-radius: 4px; font-family: monospace; }
        pre { background: #0b0f19; padding: 15px; border-radius: 4px; overflow-x: auto; color: #a5f3fc; border: 1px solid #1e293b; }
    </style>
</head>
<body>
    <div class="box">
        <h2>Host Diagnostic Console (User: operator)</h2>
        <p>Run diagnostic commands in the low-privilege environment.</p>
        <form method="POST" action="/terminal/exec">
            <span>$ </span><input type="text" name="cmd" placeholder="id, ls -la /var/log, etc." required autofocus>
            <button type="submit">Execute</button>
        </form>
        {% if output is not none %}
        <h3>Command Output:</h3>
        <pre>{{ output }}</pre>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
@app.route("/terminal/exec", methods=["POST"])
def execute_cmd():
    if request.method == "GET":
        return render_template_string(HTML_UI, output=None)

    cmd = request.form.get("cmd") or (request.json.get("cmd") if request.is_json else None)
    if not cmd:
        return jsonify({"error": "No command provided"}), 400

    # Executes strictly as low-privilege user operator
    try:
        proc = subprocess.run(
            ["su", "-", "operator", "-c", cmd],
            capture_output=True,
            text=True,
            timeout=8
        )
        output = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        output = "Error: Command timed out."
    except Exception as e:
        output = f"Execution error: {str(e)}"

    if request.is_json:
        return jsonify({"command": cmd, "output": output})
    return render_template_string(HTML_UI, output=output)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
