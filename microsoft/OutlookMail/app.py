from flask import Flask, request, jsonify
from services import OutlookMailExtractionService
from flask_cors import CORS
import os
from dotenv import load_dotenv
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=".env")

app = Flask(__name__)
CORS(app)

# Microsoft Graph API configuration
config = {
    'outlook_client_id': os.getenv('OUTLOOK_CLIENT_ID'),
    'outlook_client_secret': os.getenv('OUTLOOK_CLIENT_SECRET'),
    'tenant_id': os.getenv('TENANT_ID')
}

extraction_service = OutlookMailExtractionService()

@app.route('/api/emails/extract/start/<connection_id>', methods=['POST'])
def start_extraction(connection_id):
    logger.info(f"[START] Request received for connection_id: {connection_id}")

    if not request.is_json:
        return jsonify({"error": "Invalid JSON payload"}), 400

    data = request.get_json()
    if not isinstance(data, dict) or 'config' not in data or 'user_upn' not in data:
        return jsonify({"error": "Request must include 'config' and 'user_upn' fields"}), 400

    config_payload = data['config']
    user_upn = data['user_upn']

    # Add default values from environment if not provided
    config_payload.setdefault('tenant_id', os.getenv('TENANT_ID'))
    config_payload.setdefault('outlook_client_id', os.getenv('OUTLOOK_CLIENT_ID'))
    config_payload.setdefault('outlook_client_secret', os.getenv('OUTLOOK_CLIENT_SECRET'))

    success, message = extraction_service.start_extraction(connection_id, user_upn, config_payload)

    if success:
        logger.info(f"[START] Extraction started for connection_id: {connection_id}")
        return jsonify({
            "message": message,
            "connection_id": connection_id
        }), 202
    elif message == "Extraction already in progress":
        logger.warning(f"[START] Extraction already in progress for connection_id: {connection_id}")
        return jsonify({
            "error": message,
            "connection_id": connection_id
        }), 409  # Conflict
    else:
        logger.error(f"[START] Failed to start extraction for connection_id: {connection_id}, error: {message}")
        return jsonify({
            "error": message,
            "connection_id": connection_id
        }), 400

@app.route('/api/emails/extract/status/<connection_id>', methods=['GET'])
def extraction_status(connection_id):
    logger.info(f"[STATUS] Request for connection_id: {connection_id}")
    status = extraction_service.get_status(connection_id)
    return jsonify(status), 200

@app.route('/api/emails/extract/result/<connection_id>', methods=['GET'])
def extraction_result(connection_id):
    logger.info(f"[RESULT] Request for connection_id: {connection_id}")
    result = extraction_service.get_result(connection_id)

    if result is None:
        return jsonify({"error": "Result not ready or extraction failed."}), 202

    return jsonify({
        "connection_id": connection_id,
        "emails": result
    }), 200

@app.route('/api/emails/extract/batch/start', methods=['POST'])
def start_batch_extraction():
    logger.info("[START] Request received for batch extraction")
    try:
        if not request.is_json:
            logger.error("[START] Invalid JSON payload for batch extraction")
            return jsonify({"error": "Invalid JSON payload"}), 400

        data = request.get_json()
        if not isinstance(data, dict) or 'config' not in data or 'user_upns' not in data:
            logger.error("[START] Missing required fields for batch extraction")
            return jsonify({"error": "Request must include 'config' and 'user_upns' fields"}), 400

        config_payload = data['config']
        user_upns = data['user_upns']

        if not isinstance(user_upns, list):
            logger.error("[START] user_upns must be a list")
            return jsonify({"error": "'user_upns' must be a list"}), 400

        # Add default values from environment if not provided
        config_payload.setdefault('tenant_id', os.getenv('TENANT_ID'))
        config_payload.setdefault('outlook_client_id', os.getenv('OUTLOOK_CLIENT_ID'))
        config_payload.setdefault('outlook_client_secret', os.getenv('OUTLOOK_CLIENT_SECRET'))

        logger.info(f"[START] Processing user_upns: {user_upns}")
        success, message = extraction_service.start_batch_extraction(user_upns, config_payload)

        if success:
            batch_id = message.split(": ")[-1]
            logger.info(f"[START] Batch started: {batch_id}")
            return jsonify({
                "message": message,
                "batch_id": batch_id
            }), 202
        else:
            logger.error(f"[START] Batch start failed: {message}")
            return jsonify({
                "error": message
            }), 400
    except Exception as e:
        logger.error(f"[ERROR] Exception in start_batch_extraction: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/emails/extract/batch/status/<batch_id>', methods=['GET'])
def batch_extraction_status(batch_id):
    logger.info(f"[STATUS] Request for batch_id: {batch_id}")
    status = extraction_service.get_batch_status(batch_id)
    return jsonify(status), 200

@app.route('/api/emails/extract/batch/result/<batch_id>', methods=['GET'])
def batch_extraction_result(batch_id):
    logger.info(f"[RESULT] Request for batch_id: {batch_id}")
    result = extraction_service.get_batch_result(batch_id)

    if result is None:
        return jsonify({"error": "Result not ready or extraction failed."}), 202

    return jsonify(result), 200

# New endpoints for handling list of emails
@app.route('/api/emails/list/start', methods=['POST'])
def start_email_list_extraction():
    print("[START] Request received for email list extraction")
    
    if not request.is_json:
        return jsonify({"error": "Invalid JSON payload"}), 400

    data = request.get_json()
    if not isinstance(data, dict) or 'config' not in data or 'emails' not in data:
        return jsonify({"error": "Request must include 'config' and 'emails' fields"}), 400

    config_payload = data['config']
    emails = data['emails']

    if not isinstance(emails, list):
        return jsonify({"error": "'emails' must be a list"}), 400

    # Add default values from environment if not provided
    config_payload.setdefault('tenant_id', os.getenv('TENANT_ID'))
    config_payload.setdefault('outlook_client_id', os.getenv('OUTLOOK_CLIENT_ID'))
    config_payload.setdefault('outlook_client_secret', os.getenv('OUTLOOK_CLIENT_SECRET'))
    
    # Add emails to the config payload
    config_payload['emails'] = emails

    # Generate a unique batch ID
    batch_id = f"email_list_{int(time.time())}"
    
    success, message = extraction_service.start_batch_extraction(config_payload)

    if success:
        return jsonify({
            "message": message,
            "batch_id": batch_id
        }), 202
    else:
        return jsonify({
            "error": message
        }), 400

@app.route('/api/emails/list/status/<batch_id>', methods=['GET'])
def email_list_extraction_status(batch_id):
    print(f"[STATUS] Request for email list batch_id: {batch_id}")
    status = extraction_service.get_batch_status(batch_id)
    return jsonify(status), 200

@app.route('/api/emails/list/result/<batch_id>', methods=['GET'])
def email_list_extraction_result(batch_id):
    print(f"[RESULT] Request for email list batch_id: {batch_id}")
    result = extraction_service.get_batch_result(batch_id)

    if result is None:
        return jsonify({"error": "Result not ready or extraction failed."}), 202

    return jsonify(result), 200

@app.route('/api/emails/extract/pause/<connection_id>', methods=['POST'])
def pause_extraction(connection_id):
    logger.info(f"[PAUSE] Request for connection_id: {connection_id}")
    success, message = extraction_service.pause_extraction(connection_id)
    if success:
        logger.info(f"[PAUSE] Successfully paused extraction for connection_id: {connection_id}")
        return jsonify({"message": message}), 200
    logger.warning(f"[PAUSE] Failed to pause extraction for connection_id: {connection_id}, error: {message}")
    return jsonify({"error": message}), 404

@app.route('/api/emails/extract/continue/<connection_id>', methods=['POST'])
def continue_extraction(connection_id):
    logger.info(f"[CONTINUE] Request for connection_id: {connection_id}")
    success, message = extraction_service.continue_extraction(connection_id)
    if success:
        logger.info(f"[CONTINUE] Successfully continued extraction for connection_id: {connection_id}")
        return jsonify({"message": message}), 200
    logger.warning(f"[CONTINUE] Failed to continue extraction for connection_id: {connection_id}, error: {message}")
    return jsonify({"error": message}), 404

@app.route('/api/emails/extract/cancel/<connection_id>', methods=['POST'])
def cancel_extraction(connection_id):
    logger.info(f"[CANCEL] Request for connection_id: {connection_id}")
    success, message = extraction_service.cancel_extraction(connection_id)
    if success:
        logger.info(f"[CANCEL] Successfully cancelled extraction for connection_id: {connection_id}")
        return jsonify({"message": message}), 200
    logger.warning(f"[CANCEL] Failed to cancel extraction for connection_id: {connection_id}, error: {message}")
    return jsonify({"error": message}), 404

@app.route('/api/emails/extract/batch/pause/<batch_id>', methods=['POST'])
def pause_batch_extraction(batch_id):
    logger.info(f"[PAUSE] Request for batch_id: {batch_id}")
    success, message = extraction_service.pause_batch_extraction(batch_id)
    if success:
        logger.info(f"[PAUSE] Successfully paused batch extraction for batch_id: {batch_id}")
        return jsonify({"message": message}), 200
    logger.warning(f"[PAUSE] Failed to pause batch extraction for batch_id: {batch_id}, error: {message}")
    return jsonify({"error": message}), 404

@app.route('/api/emails/extract/batch/continue/<batch_id>', methods=['POST'])
def continue_batch_extraction(batch_id):
    logger.info(f"[CONTINUE] Request for batch_id: {batch_id}")
    success, message = extraction_service.continue_batch_extraction(batch_id)
    if success:
        logger.info(f"[CONTINUE] Successfully continued batch extraction for batch_id: {batch_id}")
        return jsonify({"message": message}), 200
    logger.warning(f"[CONTINUE] Failed to continue batch extraction for batch_id: {batch_id}, error: {message}")
    return jsonify({"error": message}), 404

@app.route('/api/emails/extract/batch/cancel/<batch_id>', methods=['POST'])
def cancel_batch_extraction(batch_id):
    logger.info(f"[CANCEL] Request for batch_id: {batch_id}")
    success, message = extraction_service.cancel_batch_extraction(batch_id)
    if success:
        logger.info(f"[CANCEL] Successfully cancelled batch extraction for batch_id: {batch_id}")
        return jsonify({"message": message}), 200
    logger.warning(f"[CANCEL] Failed to cancel batch extraction for batch_id: {batch_id}, error: {message}")
    return jsonify({"error": message}), 404

if __name__ == '__main__':
    app.run(port=3006, debug=True) 