from flask import Flask, request, jsonify
from services import MicrosoftDocumentActivityService
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

document_extraction_service = MicrosoftDocumentActivityService()

@app.route('/api/documentactivity/start/<connection_id>', methods=['POST'])
def start_activity(connection_id):
    print(f"[START ACTIVITY] Request received for connection_id: {connection_id}")

    if not request.is_json:
        return jsonify({"error": "Invalid JSON payload"}), 400

    config_payload = request.get_json()
    success, message = document_extraction_service.start_activity(connection_id, config_payload)

    if success:
        return jsonify({
            "message": message,
            "connection_id": connection_id
        }), 202
    elif message == "Activity check already in progress":
        return jsonify({
            "error": message,
            "connection_id": connection_id
        }), 409
    else:
        return jsonify({
            "error": message,
            "connection_id": connection_id
        }), 400


@app.route('/api/documentactivity/status/<connection_id>', methods=['GET'])
def activity_status(connection_id):
    print(f"[STATUS ACTIVITY] Request for connection_id: {connection_id}")
    status = document_extraction_service.get_status(connection_id)
    return jsonify(status), 200


@app.route('/api/documentactivity/result/<connection_id>', methods=['GET'])
def activity_result(connection_id):
    print(f"[RESULT ACTIVITY] Request for connection_id: {connection_id}")
    result = document_extraction_service.get_result(connection_id)

    if result is None:
        return jsonify({"error": "Result not ready or activity check failed."}), 202

    return jsonify({
        "connection_id": connection_id,
        "activity": result
    }), 200

if __name__ == '__main__':
    app.run(port=3006, debug=True)