from flask import Flask, request, render_template_string
import subprocess, re

app = Flask(__name__)

HTML = """
<!doctype html>
<html>
<head><title>Hardened Health Monitor</title></head>
<body style="font-family: Arial; margin: 40px;">
  <h2>Defense-in-Depth Node Healthcheck</h2>
  <form method="POST">
    <input name="node" placeholder="node-id or IP" style="width: 250px; padding: 6px;">
    <button type="submit">Verify</button>
  </form>
  {% if result %}
  <h3>Result:</h3>
  <pre style="background: #eee; padding: 15px;">{{ result }}</pre>
  {% endif %}
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    result = ""
    if request.method == "POST":
        node = request.form.get("node", "")
        if any(c in node for c in [" ", ";", "&&", "||", "|", "`"]):
            result = "ERROR: Illegal characters detected."
        else:
            try:
                cmd = f"ping -c 1 {node}"
                result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True, timeout=5)
            except Exception as e:
                result = str(e)
    return render_template_string(HTML, result=result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888)
