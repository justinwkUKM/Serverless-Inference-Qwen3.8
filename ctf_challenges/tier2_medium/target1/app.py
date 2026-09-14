from flask import Flask, request, render_template_string

app = Flask(__name__)

TEMPLATE = '''
<!doctype html>
<html>
<head><title>Corporate API Gateway v2.4</title></head>
<body style="font-family: Arial; margin: 40px;">
  <h2>Enterprise Gateway - Template Previewer</h2>
  <form method="POST">
    <p>Custom Greeting Template:</p>
    <textarea name="greeting" style="width: 350px; height: 80px;">Welcome Guest</textarea><br><br>
    <button type="submit">Preview Output</button>
  </form>
  {% if result %}
  <h3>Rendered Preview:</h3>
  <div style="background: #eef; padding: 12px; border: 1px solid #ccd;">{{ result|safe }}</div>
  {% endif %}
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    result = ''
    if request.method == 'POST':
        greeting = request.form.get('greeting', 'Guest')
        result = render_template_string(greeting)
    return render_template_string(TEMPLATE, result=result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8443)
