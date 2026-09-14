from flask import Flask, request, render_template_string
import subprocess

app = Flask(__name__)

TEMPLATE = '''
<!doctype html>
<html>
<head><title>Internal Diagnostic Portal</title></head>
<body style="font-family: Arial; margin: 40px;">
  <h2>Ops Diagnostics Service</h2>
  <p>Ping internal gateway or interfaces:</p>
  <form method="POST">
    <input name="host" placeholder="e.g. 127.0.0.1" style="width: 250px; padding: 6px;">
    <button type="submit" style="padding: 6px 12px;">Diagnose</button>
  </form>
  {% if output %}
  <h3>Result:</h3>
  <pre style="background: #eee; padding: 10px; border-radius: 4px;">{{ output }}</pre>
  {% endif %}
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    output = ''
    if request.method == 'POST':
        host = request.form.get('host', '')
        cmd = f'ping -c 1 {host}'
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True, timeout=5)
        except Exception as e:
            output = str(e)
    return render_template_string(TEMPLATE, output=output)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
