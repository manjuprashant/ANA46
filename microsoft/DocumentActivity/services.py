import threading
import requests
import time
import json
import os
import tempfile

class MicrosoftDocumentActivityService:
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
        with tempfile.NamedTemporaryFile('w', delete=False) as tf:
            json.dump(self._store, tf, indent=2)
            tempname = tf.name
        os.replace(tempname, self.STORE_FILE)

    def start_activity(self, connection_id, config_payload):
        existing = self._store.get(connection_id)
        if existing:
            if existing['status'] == 'in_progress':
                return False, "Activity check already in progress"
            elif existing['status'] == 'completed':
                return False, "Activity check already completed"
            elif existing['status'] == 'failed':
                pass  # allow retry

        self._store[connection_id] = {
            'status': 'in_progress',
            'config': config_payload,
            'result': None,
            'error': None,
            'started_at': time.time(),
        }
        self._save_store()

        thread = threading.Thread(target=self._fetch_document_activity, args=(connection_id,))
        thread.start()

        return True, "Document activity check started"
    
    def _fetch_document_activity(self, connection_id):
        try:
            config = self._store[connection_id]['config']

            token = self._get_access_token(
                tenant_id=config['tenant_id'],
                client_id=config['client_id'],
                client_secret=config['client_secret'],
                scopes=["https://graph.microsoft.com/.default "]
            )

            users = self._get_all_users(token)
            all_activities = []

            for user in users:
                user_id = user['id']
                user_principal_name = user['userPrincipalName']

                try:
                    # Get recent files
                    recent_files = self._get_recent_files(token, user_id)

                    # Get shared files
                    shared_files = self._get_shared_files(token, user_id)

                    # Combine into activity data
                    user_activity = {
                        "user": user_principal_name,
                        "recent_files": recent_files,
                        "shared_files": shared_files
                    }

                    all_activities.append(user_activity)
                except Exception as e:
                    print(f"Failed to fetch activity for {user_principal_name}: {str(e)}")

            self._store[connection_id].update({
                'status': 'completed',
                'result': all_activities,
                'completed_at': time.time()
            })
        except Exception as e:
            self._store[connection_id].update({
                'status': 'failed',
                'error': str(e),
                'completed_at': time.time()
            })
        finally:
            self._save_store()
        
    def _get_access_token(self, tenant_id, client_id, client_secret, scopes):
        url = f"https://login.microsoftonline.com/ {tenant_id}/oauth2/v2.0/token"
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
        headers = {'Authorization': f'Bearer {access_token}'}
        url = 'https://graph.microsoft.com/v1.0/users '
        users = []

        while url:
            res = requests.get(url, headers=headers)
            res.raise_for_status()
            data = res.json()
            users.extend(data.get('value', []))
            url = data.get('@odata.nextLink')

        return users
    
    def _get_recent_files(self, access_token, user_id):
        headers = {'Authorization': f'Bearer {access_token}'}
        url = f'https://graph.microsoft.com/v1.0/users/ {user_id}/drive/recent'
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        return res.json().get('value', [])
    
    def _get_shared_files(self, access_token, user_id):
        headers = {'Authorization': f'Bearer {access_token}'}
        url = f'https://graph.microsoft.com/v1.0/users/ {user_id}/drive/sharedWithMe'
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        return res.json().get('value', [])
    
    def get_status(self, connection_id):
        info = self._store.get(connection_id)
        if not info:
            return {"status": "not_started"}
        return {
            "status": info.get("status"),
            "started_at": info.get("started_at"),
            "completed_at": info.get("completed_at"),
            "error": info.get("error")
        }
    
    def get_result(self, connection_id):
        info = self._store.get(connection_id)
        if not info or info.get("status") != "completed":
            return None
        return info.get("result")