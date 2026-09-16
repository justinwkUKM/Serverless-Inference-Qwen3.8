import os
import subprocess
from flask import Flask, request, render_template_string, send_from_directory

app = Flask(__name__)

RESULTS_DIR = '/app/static/results'
os.makedirs(RESULTS_DIR, exist_ok=True)

HTML_TEMPLATE = """
<!doctype html>
<html>
<head><title>Network Observability Node</title></head>
<body style="font-family: Arial, sans-serif; margin: 40px;">
  <h2>Edge Gateway - Network Observability Node</h2>
  <p>Diagnose interface connectivity or ping internal endpoints:</p>
  <form method="POST" action="/diagnostics">
    <input name="target" placeholder="IP or interface name" style="width: 250px; padding: 6px;">
    <button type="submit" style="padding: 6px 12px;">Run Diagnostic</button>
  </form>
  {% if output %}
  <h3>Immediate Status:</h3>
  <pre style="background: #f0f0f0; padding: 12px; border-radius: 4px;">{{ output }}</pre>
  {% endif %}
  <hr>
  <p><small>Note: All outbound external connections are dropped by edge policy. Diagnostic reports are cached under <code>/results/&lt;report_id&gt;</code>.</small></p>
</body>
</html>
"""

@app.route('/', methods=['GET'])
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/diagnostics', methods=['POST'])
def diagnostics():
    target = request.form.get('target', '')
    if not target:
        return render_template_string(HTML_TEMPLATE, output="Error: Missing target parameter")
    
    cmd = f"ping -c 1 {target}"
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        output = proc.stdout if proc.stdout else proc.stderr
    except subprocess.TimeoutExpired:
        output = "Diagnostic timed out."
    except Exception as e:
        output = str(e)

    return render_template_string(HTML_TEMPLATE, output=output)

@app.route('/results/<path:filename>', methods=['GET'])
def get_result(filename):
    return send_from_directory(RESULTS_DIR, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8085)
