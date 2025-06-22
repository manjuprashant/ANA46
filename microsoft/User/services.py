import threading
import requests
import time
import json
import os
import tempfile

class MicrosoftExtractionService:
    STORE_FILE = "store.json"

    def __init__(self):
        self._store = self._load_store()

    def _load_store(self):
        if os.path.exists(self.STORE_FILE):
            with open(self.STORE_FILE, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def _save_store(self):
        # Create temp file in the same directory as store.json to avoid cross-drive issues
        store_dir = os.path.dirname(os.path.abspath(self.STORE_FILE))
        
        with tempfile.NamedTemporaryFile('w', delete=False, dir=store_dir, suffix='.tmp') as tf:
            json.dump(self._store, tf, indent=2)
            tempname = tf.name
        
        try:
            os.replace(tempname, self.STORE_FILE)
        except Exception as e:
            # Clean up temp file if replace fails
            if os.path.exists(tempname):
                os.remove(tempname)
            raise e


    def start_extraction(self, connection_id, config_payload):
        existing = self._store.get(connection_id)
        if existing:
            if existing['status'] == 'in_progress':
                return False, "Extraction already in progress"
            elif existing['status'] == 'completed':
                return False, "Extraction already completed"
            elif existing['status'] == 'failed':
                # Allow retry if failed
                pass

        self._store[connection_id] = {
            'status': 'in_progress',
            'config': config_payload,
            'result': None,
            'error': None,
            'started_at': time.time(),
        }
        self._save_store()

        thread = threading.Thread(target=self._extract_users, args=(connection_id,))
        thread.start()

        return True, "Extraction started"

    def _extract_users(self, connection_id):
        try:
            config = self._store[connection_id]['config']

            token = self._get_access_token(
                tenant_id=config['tenant_id'],
                client_id=config['client_id'],
                client_secret=config['client_secret'],
                scopes=["https://graph.microsoft.com/.default"]
            )

            users = self._get_all_users(token)

            self._store[connection_id].update({
                'status': 'completed',
                'result': users,
                'completed_at': time.time(),
            })
        except Exception as e:
            self._store[connection_id].update({
                'status': 'failed',
                'error': str(e),
                'completed_at': time.time(),
            })
        finally:
            self._save_store()

    def _get_access_token(self, tenant_id, client_id, client_secret, scopes):
        url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": " ".join(scopes)
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(url, data=data, headers=headers)
        response.raise_for_status()
        return response.json().get("access_token")

    def _get_all_users(self, access_token):
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        url = 'https://graph.microsoft.com/v1.0/users'
        users = []

        while url:
            res = requests.get(url, headers=headers)
            res.raise_for_status()
            data = res.json()
            users.extend(data.get('value', []))
            url = data.get('@odata.nextLink')

        return users

    def get_status(self, connection_id):
        info = self._store.get(connection_id)
        if not info:
            return {"status": "not_started"}  # No extraction started for this ID
        
        # Return current status, with optional timestamps and error if any
        return {
            "status": info.get("status", "unknown"),
            "started_at": info.get("started_at"),
            "completed_at": info.get("completed_at"),
            "error": info.get("error"),
        }

    def get_result(self, connection_id):
        info = self._store.get(connection_id)
        if not info:
            return None  # No extraction started
        
        # Only return the result if extraction completed successfully
        if info.get("status") == "completed":
            return info.get("result")
        
        # Otherwise return None explicitly to indicate no result available yet or failed
        return None