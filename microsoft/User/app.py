from flask import Flask, request, jsonify
from services import MicrosoftExtractionService
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

extraction_service = MicrosoftExtractionService()

@app.route('/api/extract/start/<connection_id>', methods=['POST'])
def start_extraction(connection_id):
    print(f"[START] Request received for connection_id: {connection_id}")

    if not request.is_json:
        return jsonify({"error": "Invalid JSON payload"}), 400

    config_payload = request.get_json()
    success, message = extraction_service.start_extraction(connection_id, config_payload)

    if success:
        return jsonify({
            "message": message,
            "connection_id": connection_id
        }), 202
    elif message == "Extraction already in progress":
        return jsonify({
            "error": message,
            "connection_id": connection_id
        }), 409  # Conflict
    else:
        return jsonify({
            "error": message,
            "connection_id": connection_id
        }), 400

@app.route('/api/extract/status/<connection_id>', methods=['GET'])
def extraction_status(connection_id):
    print(f"[STATUS] Request for connection_id: {connection_id}")
    status = extraction_service.get_status(connection_id)
    return jsonify(status), 200

@app.route('/api/extract/result/<connection_id>', methods=['GET'])
def extraction_result(connection_id):
    print(f"[RESULT] Request for connection_id: {connection_id}")
    result = extraction_service.get_result(connection_id)

    if result is None:
        return jsonify({"error": "Result not ready or extraction failed."}), 202

    return jsonify({
        "connection_id": connection_id,
        "users": result
    }), 200

if __name__ == '__main__':
    app.run(port=3005, debug=True)
