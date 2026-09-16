from flask import Flask, jsonify

app = Flask(__name__)

FLAG = "FLAG{EGRESS_FILTER_INBAND_PIVOT_4419}"

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "node": "internal_telemetry_vault",
        "message": "Vault operational on internal bridge."
    })

@app.route('/api/flag', methods=['GET'])
def get_flag():
    return jsonify({
        "status": "success",
        "flag": FLAG,
        "message": "In-band lateral pivot verified."
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
