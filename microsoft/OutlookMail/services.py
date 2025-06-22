import threading
import requests
import time
import json
import os
import tempfile
from datetime import datetime
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor
import signal
import sys
import psycopg2
from dateutil.parser import parse
from db_utils import EmailDB

class OutlookMailExtractionService:
    STORE_FILE = "store.json"
    GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
    NO_MORE_EMAILS_FILE = "no_more_emails.json"
    SKIPPED_EMAILS_FOLDER = "skipped_emails"
    EMAIL_JSON_FOLDER = "email_json"
    PROCESSED_USERS_FILE = "processed_users.json"

    def __init__(self, db_config=None):
        self._store = self._load_store()
        self._db_config = db_config
        self.db = EmailDB()
        self.paused_tasks = set()
        self.cancelled_tasks = set()
        self.active_threads = {}  # Track active extraction threads
        self.pause_events = {}  # Event objects for pausing threads
        os.makedirs(self.SKIPPED_EMAILS_FOLDER, exist_ok=True)
        os.makedirs(self.EMAIL_JSON_FOLDER, exist_ok=True)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, sig, frame):
        print(f"\nThread: {threading.current_thread().name} - Script interrupted.")
        sys.exit(0)

    def _load_store(self):
        if os.path.exists(self.STORE_FILE):
            with open(self.STORE_FILE, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def _save_store(self):
        # Convert sets to lists for JSON serialization
        store_copy = {}
        for key, value in self._store.items():
            if isinstance(value, dict):
                store_copy[key] = {
                    k: list(v) if isinstance(v, set) else v 
                    for k, v in value.items()
                }
            else:
                store_copy[key] = value
        
        # Create temp file in the same directory as store.json to avoid cross-drive issues
        store_dir = os.path.dirname(os.path.abspath(self.STORE_FILE))
        
        with tempfile.NamedTemporaryFile('w', delete=False, dir=store_dir, suffix='.tmp') as tf:
            json.dump(store_copy, tf, indent=2)
            tempname = tf.name
        
        try:
            os.replace(tempname, self.STORE_FILE)
        except Exception as e:
            # Clean up temp file if replace fails
            if os.path.exists(tempname):
                os.remove(tempname)
            raise e


        

    def _load_processed_users(self):
        return self.db.get_processed_users()

    def _save_processed_users(self, processed_users):
        # No need to save processed users separately as they are tracked in the emails table
        pass

    def _record_no_more_emails(self, user_upn):
        self.db.add_no_more_emails_user(user_upn)
        print(f"Thread: {threading.current_thread().name} - Recorded '{user_upn}' as no emails were found.")

    def _is_user_in_no_more_emails(self, user_upn):
        if self.db.is_user_in_no_more_emails(user_upn):
            print(f"Thread: {threading.current_thread().name} - Skipping user '{user_upn}' as they are marked as having no more emails.")
            return True
        return False

    def get_analyzable_users(self):
        print("[DEBUG] Entered get_analyzable_users")
        try:
            # Get all users from the emails table
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Get users who have emails
            cursor.execute("""
                SELECT DISTINCT user_upn 
                FROM emails
            """)
            users_with_emails = {row[0] for row in cursor.fetchall()}
            
            # Get users marked as having no more emails
            cursor.execute("""
                SELECT user_upn 
                FROM no_more_emails
            """)
            users_no_more_emails = {row[0] for row in cursor.fetchall()}
            
            # Get users from skipped emails
            cursor.execute("""
                SELECT DISTINCT user_upn 
                FROM skipped_emails
            """)
            users_with_skipped = {row[0] for row in cursor.fetchall()}
            
            # Combine all users
            all_users = users_with_emails.union(users_with_skipped)
            
            # Remove users who are marked as having no more emails
            analyzable_users = all_users - users_no_more_emails
            
            cursor.close()
            conn.close()
            
            print(f"[DEBUG] Found users: {analyzable_users}")
            return list(analyzable_users)
        except Exception as e:
            print(f"[ERROR] Exception in get_analyzable_users: {e}")
            raise

    def start_extraction(self, connection_id, user_upn, config_payload):
        """Start extraction for a single user"""
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
            'user_upn': user_upn,
            'result': None,
            'error': None,
            'started_at': time.time(),
            'processed_message_ids': set(),
            'skipped_message_ids': set()
        }
        self._save_store()

        thread = threading.Thread(target=self._extract_emails, args=(connection_id,))
        thread.daemon = True
        self.active_threads[connection_id] = thread
        thread.start()

        return True, "Extraction started"

    def start_batch_extraction(self, user_upns, config_payload):
        print("[DEBUG] Entered start_batch_extraction")
        try:
            if not user_upns:
                print("[DEBUG] No users provided")
                return False, "No users to process"

            if not isinstance(user_upns, list):
                user_upns = [user_upns]

            print(f"[DEBUG] Processing provided user list: {user_upns}")

            batch_id = f"batch_{int(time.time())}"
            self._store[batch_id] = {
                'status': 'in_progress',
                'config': config_payload,
                'users': user_upns,
                'processed_users': [],
                'failed_users': [],
                'started_at': time.time(),
                'completed_at': None,
                'error': None
            }
            self._save_store()

            thread = threading.Thread(target=self._process_batch, args=(batch_id,))
            thread.daemon = True
            self.active_threads[batch_id] = thread
            thread.start()
            print(f"[DEBUG] Batch thread started: {batch_id}")

            return True, f"Batch extraction started with ID: {batch_id}"
        except Exception as e:
            print(f"[ERROR] Exception in start_batch_extraction: {e}")
            return False, str(e)

    def _get_access_token(self, tenant_id, outlook_client_id, outlook_client_secret, scopes):
        url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": outlook_client_id,
            "client_secret": outlook_client_secret,
            "scope": " ".join(scopes)
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(url, data=data, headers=headers)
        response.raise_for_status()
        return response.json().get("access_token")

    def _fetch_message_ids(self, user_upn, access_token, folder_name=None, skip_pages=0):
        """Fetch all message metadata (IDs) for a user using pagination, with an option to skip initial pages."""
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Use folder-specific endpoint if provided, otherwise get all messages
        if folder_name:
            url = f"{self.GRAPH_API_ENDPOINT}/users/{user_upn}/mailFolders/{folder_name}/messages?$select=id&$top=500"
        else:
            url = f"{self.GRAPH_API_ENDPOINT}/users/{user_upn}/messages?$select=id&$top=500"

        all_ids = []
        page_count = 0
        max_pages = 2  # Increased safety cap
        skipped_count = 0  # Number of pages to skip

        while url and page_count < max_pages:
            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                data = response.json()

                if skipped_count < skip_pages:
                    print(f"Thread: {threading.current_thread().name} - Skipping page {page_count + 1} for {user_upn}...")
                    url = data.get("@odata.nextLink")
                    page_count += 1
                    skipped_count += 1
                    continue  # Skip processing this page's IDs

                message_batch = [msg["id"] for msg in data.get("value", [])]
                all_ids.extend(message_batch)

                page_count += 1
                print(f"Thread: {threading.current_thread().name} - Fetched {len(message_batch)} email IDs (Page {page_count}) for {user_upn} from {folder_name or 'all folders'}...")

                url = data.get("@odata.nextLink")

            except requests.exceptions.RequestException as e:
                print(f"Thread: {threading.current_thread().name} - Error fetching IDs for {user_upn} on page {page_count} from {folder_name or 'all folders'}: {e}")
                return all_ids

        if page_count >= max_pages and url:
            print(f"Thread: {threading.current_thread().name} - Warning: Reached maximum page limit ({max_pages}) while fetching IDs for {user_upn} from {folder_name or 'all folders'}. Some emails might have been skipped.")

        return all_ids

    def _fetch_inbox_messages(self, user_upn, access_token, skip_pages=0):
        return self._fetch_message_ids(user_upn, access_token, folder_name="Inbox", skip_pages=skip_pages)

    def _fetch_sent_messages(self, user_upn, access_token, skip_pages=0):
        return self._fetch_message_ids(user_upn, access_token, folder_name="SentItems", skip_pages=skip_pages)

    def _fetch_full_message(self, user_upn, message_id, access_token):
        """Fetch the full message content for a given message ID."""
        headers = {"Authorization": f"Bearer {access_token}"}
        url = f"{self.GRAPH_API_ENDPOINT}/users/{user_upn}/messages/{message_id}"

        for attempt in range(3):
            try:
                response = requests.get(url, headers=headers, timeout=30)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 5))
                    print(f"429 rate limit hit. Retrying after {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                print(f"Error fetching message {message_id} for {user_upn}: {e}")
                time.sleep(2)
                continue

        return None

    def _html_to_text(self, html_content):
        if not html_content:
            return ""
        soup = BeautifulSoup(html_content, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        for tag in soup.find_all(True):
            tag.attrs = {}
        text = soup.get_text(separator="\n")
        return re.sub(r"\n+", "\n", text).strip()

    def _log_skipped_email(self, email, user_upn, reason):
        self.db.save_skipped_email(
            user_upn=user_upn,
            message_id=email.get("id"),
            from_address=email.get("from", {}).get("emailAddress", {}).get("address", "Unknown Sender"),
            subject=email.get("subject"),
            reason=reason
        )

    def _process_message_batch(self, user_upn, message_ids, access_token, processed_ids, skipped_ids, source_folder=None):
        results = []
        for message_id in message_ids:
            if message_id in processed_ids or message_id in skipped_ids:
                continue

            print(f"Thread: {threading.current_thread().name} - Processing message ID {message_id} for user: {user_upn}")
            email = self._fetch_full_message(user_upn, message_id, access_token)

            if not email:
                print(f"Thread: {threading.current_thread().name} - Could not fetch full message for ID: {message_id} for user: {user_upn}")
                continue

            sender = email.get("from", {}).get("emailAddress", {}).get("address", "Unknown Sender")
            to_recipients_list = [r["emailAddress"]["address"].lower() for r in email.get("toRecipients", []) if "emailAddress" in r]

            if user_upn.lower() not in to_recipients_list and sender.lower() != user_upn.lower():
                print(f"Thread: {threading.current_thread().name} - Skipping message ID: {message_id} for user: {user_upn} (not to or from user)")
                self._log_skipped_email(email, user_upn, reason="Not to or from the user")
                skipped_ids.add(message_id)
                continue

            # Save the email to the database
            self.db.save_email(email, user_upn, source_folder or ('inbox' if message_id in self._fetch_message_ids(user_upn, access_token, "Inbox") else 'sent'))
            processed_ids.add(message_id)
            results.append(email)

        return results

    def _check_pause(self, task_id):
        """Check if task is paused and wait if it is"""
        if task_id in self.paused_tasks:
            if task_id not in self.pause_events:
                self.pause_events[task_id] = threading.Event()
            self.pause_events[task_id].clear()
            print(f"Thread: {threading.current_thread().name} - Task {task_id} is paused, waiting...")
            self.pause_events[task_id].wait()  # Wait until event is set
            print(f"Thread: {threading.current_thread().name} - Task {task_id} resumed")

    def _extract_emails(self, connection_id):
        """Extract emails for a single user"""
        try:
            config = self._store[connection_id]['config']
            user_upn = config.get('user_upn')

            if not user_upn:
                raise ValueError("user_upn is required in config")

            # Check if task is cancelled
            if connection_id in self.cancelled_tasks:
                self._store[connection_id].update({
                    'status': 'cancelled',
                    'completed_at': time.time(),
                })
                self._save_store()
                return

            # Check if task is paused
            self._check_pause(connection_id)

            if self._is_user_in_no_more_emails(user_upn):
                self._store[connection_id].update({
                    'status': 'completed',
                    'result': [],
                    'completed_at': time.time(),
                })
                return

            token = self._get_access_token(
                tenant_id=config['tenant_id'],
                outlook_client_id=config['outlook_client_id'],
                outlook_client_secret=config['outlook_client_secret'],
                scopes=["https://graph.microsoft.com/.default"]
            )

            # Get existing and skipped message IDs from the database
            existing_message_ids = self.db.get_existing_message_ids(user_upn)
            skipped_message_ids = self.db.get_skipped_message_ids(user_upn)

            # Fetch messages from both inbox and sent items
            inbox_ids = self._fetch_inbox_messages(user_upn, token)
            sent_ids = self._fetch_sent_messages(user_upn, token)

            # Check for pause after each major operation
            self._check_pause(connection_id)

            if not inbox_ids and not sent_ids:
                self._record_no_more_emails(user_upn)
                self._store[connection_id].update({
                    'status': 'completed',
                    'result': [],
                    'completed_at': time.time(),
                })
                return

            # Track which messages are in inbox, sent, or both
            inbox_message_set = set(inbox_ids)
            sent_message_set = set(sent_ids)
            both_message_ids = inbox_message_set.intersection(sent_message_set)
            only_inbox_message_ids = inbox_message_set - both_message_ids
            only_sent_message_ids = sent_message_set - both_message_ids

            # Filter out already processed messages
            new_message_ids_to_process = [
                mid for mid in inbox_message_set.union(sent_message_set)
                if mid not in existing_message_ids and mid not in skipped_message_ids
            ]

            if not new_message_ids_to_process:
                self._store[connection_id].update({
                    'status': 'completed',
                    'result': [],
                    'completed_at': time.time(),
                })
                return

            # Process messages in batches
            processed_ids = set()
            skipped_ids = set()
            all_emails = []
            batch_size = 20

            with ThreadPoolExecutor(max_workers=8) as executor:
                # Process inbox-only messages
                inbox_only_to_process = [mid for mid in only_inbox_message_ids if mid in new_message_ids_to_process]
                inbox_batches = [inbox_only_to_process[i:i + batch_size] for i in range(0, len(inbox_only_to_process), batch_size)]
                inbox_futures = [
                    executor.submit(
                        self._process_message_batch,
                        user_upn,
                        batch,
                        token,
                        processed_ids,
                        skipped_ids,
                        "inbox"
                    )
                    for batch in inbox_batches
                ]

                # Process sent-only messages
                sent_only_to_process = [mid for mid in only_sent_message_ids if mid in new_message_ids_to_process]
                sent_batches = [sent_only_to_process[i:i + batch_size] for i in range(0, len(sent_only_to_process), batch_size)]
                sent_futures = [
                    executor.submit(
                        self._process_message_batch,
                        user_upn,
                        batch,
                        token,
                        processed_ids,
                        skipped_ids,
                        "sent"
                    )
                    for batch in sent_batches
                ]

                # Process messages that appear in both folders
                both_to_process = [mid for mid in both_message_ids if mid in new_message_ids_to_process]
                both_batches = [both_to_process[i:i + batch_size] for i in range(0, len(both_to_process), batch_size)]
                both_futures = [
                    executor.submit(
                        self._process_message_batch,
                        user_upn,
                        batch,
                        token,
                        processed_ids,
                        skipped_ids,
                        "both"
                    )
                    for batch in both_batches
                ]

                # Collect all futures
                all_futures = inbox_futures + sent_futures + both_futures

                # Process results as they complete
                for future in all_futures:
                    batch_results = future.result()
                    all_emails.extend(batch_results)

            self._store[connection_id].update({
                'status': 'completed',
                'result': all_emails,
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
            # Clean up the thread reference and pause event
            if connection_id in self.active_threads:
                del self.active_threads[connection_id]
            if connection_id in self.pause_events:
                del self.pause_events[connection_id]

    def _process_batch(self, batch_id):
        """Process a batch of users"""
        try:
            batch_info = self._store[batch_id]
            config = batch_info['config']
            users = batch_info['users']
            processed_users = self._load_processed_users()

            # Check if batch is cancelled
            if batch_id in self.cancelled_tasks:
                batch_info.update({
                    'status': 'cancelled',
                    'completed_at': time.time()
                })
                self._save_store()
                return

            # Check if batch is paused
            self._check_pause(batch_id)

            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = []
                for user in users:
                    # Check for pause before processing each user
                    self._check_pause(batch_id)
                    
                    if user not in processed_users:
                        futures.append(executor.submit(self._process_user, user, config))

                for future in futures:
                    # Check for pause before processing each future
                    self._check_pause(batch_id)
                    
                    try:
                        user, success = future.result()
                        if success:
                            batch_info['processed_users'].append(user)
                            processed_users.add(user)
                        else:
                            batch_info['failed_users'].append(user)
                    except Exception as e:
                        print(f"Thread: {threading.current_thread().name} - Error processing user: {e}")

            # Only save processed users if we're not using a provided email list
            if 'emails' not in config:
                self._save_processed_users(processed_users)

            batch_info.update({
                'status': 'completed',
                'completed_at': time.time()
            })
        except Exception as e:
            batch_info.update({
                'status': 'failed',
                'error': str(e),
                'completed_at': time.time()
            })
        finally:
            self._save_store()
            # Clean up the thread reference and pause event
            if batch_id in self.active_threads:
                del self.active_threads[batch_id]
            if batch_id in self.pause_events:
                del self.pause_events[batch_id]

    def _process_user(self, user_upn, config):
        """Process a single user's emails"""
        try:
            time.sleep(30)  # Artificial delay increased to 30 seconds for testing pause/cancel/continue
            if self._is_user_in_no_more_emails(user_upn):
                return user_upn, True

            token = self._get_access_token(
                tenant_id=config['tenant_id'],
                outlook_client_id=config['outlook_client_id'],
                outlook_client_secret=config['outlook_client_secret'],
                scopes=["https://graph.microsoft.com/.default"]
            )

            # Load existing and skipped message IDs
            existing_message_ids = set()
            skipped_message_ids = set()

            # Load processed email IDs from existing JSON files
            for filename in os.listdir(self.EMAIL_JSON_FOLDER):
                if filename.startswith(f"emails_{user_upn.replace('@', '_at_')}") and filename.endswith(".json"):
                    filepath = os.path.join(self.EMAIL_JSON_FOLDER, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            for email_data in data:
                                if "id" in email_data:
                                    existing_message_ids.add(email_data["id"])
                    except Exception as e:
                        print(f"Thread: {threading.current_thread().name} - Error reading existing JSON file {filename}: {e}")

            # Load skipped message IDs
            skipped_filename = f"{user_upn.replace('@', '_at_').replace('.', '_dot_')}.json"
            skipped_filepath = os.path.join(self.SKIPPED_EMAILS_FOLDER, skipped_filename)
            if os.path.exists(skipped_filepath):
                try:
                    with open(skipped_filepath, "r", encoding="utf-8") as f:
                        skipped_data = json.load(f)
                        for entry in skipped_data:
                            if "message_id" in entry:
                                skipped_message_ids.add(entry["message_id"])
                except Exception as e:
                    print(f"Thread: {threading.current_thread().name} - Error reading skipped email file: {e}")

            # Fetch messages from both inbox and sent items using the specific methods
            inbox_ids = self._fetch_inbox_messages(user_upn, token)
            sent_ids = self._fetch_sent_messages(user_upn, token)

            if not inbox_ids and not sent_ids:
                self._record_no_more_emails(user_upn)
                return user_upn, True

            # Track which messages are in inbox, sent, or both
            inbox_message_set = set(inbox_ids)
            sent_message_set = set(sent_ids)
            both_message_ids = inbox_message_set.intersection(sent_message_set)
            only_inbox_message_ids = inbox_message_set - both_message_ids
            only_sent_message_ids = sent_message_set - both_message_ids

            # Filter out already processed messages
            new_message_ids_to_process = [
                mid for mid in inbox_message_set.union(sent_message_set)
                if mid not in existing_message_ids and mid not in skipped_message_ids
            ]

            if not new_message_ids_to_process:
                return user_upn, True

            # Process messages in batches
            processed_ids = set()
            skipped_ids = set()
            all_emails = []
            batch_size = 20

            with ThreadPoolExecutor(max_workers=8) as executor:
                # Process inbox-only messages
                inbox_only_to_process = [mid for mid in only_inbox_message_ids if mid in new_message_ids_to_process]
                inbox_batches = [inbox_only_to_process[i:i + batch_size] for i in range(0, len(inbox_only_to_process), batch_size)]
                inbox_futures = [
                    executor.submit(
                        self._process_message_batch,
                        user_upn,
                        batch,
                        token,
                        processed_ids,
                        skipped_ids,
                        "inbox"
                    )
                    for batch in inbox_batches
                ]

                # Process sent-only messages
                sent_only_to_process = [mid for mid in only_sent_message_ids if mid in new_message_ids_to_process]
                sent_batches = [sent_only_to_process[i:i + batch_size] for i in range(0, len(sent_only_to_process), batch_size)]
                sent_futures = [
                    executor.submit(
                        self._process_message_batch,
                        user_upn,
                        batch,
                        token,
                        processed_ids,
                        skipped_ids,
                        "sent"
                    )
                    for batch in sent_batches
                ]

                # Process messages that appear in both folders
                both_to_process = [mid for mid in both_message_ids if mid in new_message_ids_to_process]
                both_batches = [both_to_process[i:i + batch_size] for i in range(0, len(both_to_process), batch_size)]
                both_futures = [
                    executor.submit(
                        self._process_message_batch,
                        user_upn,
                        batch,
                        token,
                        processed_ids,
                        skipped_ids,
                        "both"
                    )
                    for batch in both_batches
                ]

                # Collect all futures
                all_futures = inbox_futures + sent_futures + both_futures

                # Process results as they complete
                for future in all_futures:
                    batch_results = future.result()
                    all_emails.extend(batch_results)

            # Save emails to JSON file
            if all_emails:
                file_path = os.path.join(self.EMAIL_JSON_FOLDER, f"emails_{user_upn.replace('@', '_at_')}.json")
                existing_emails = []

                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        try:
                            existing_emails = json.load(f)
                        except json.JSONDecodeError:
                            existing_emails = []

                updated_emails = existing_emails + all_emails
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(updated_emails, f, indent=2)

            return user_upn, True
        except Exception as e:
            print(f"Thread: {threading.current_thread().name} - Error processing user {user_upn}: {e}")
            return user_upn, False

    def get_status(self, connection_id):
        """Get status of a single user extraction"""
        info = self._store.get(connection_id)
        if not info:
            return {"status": "not_started"}
        
        return {
            "status": info.get("status", "unknown"),
            "started_at": info.get("started_at"),
            "completed_at": info.get("completed_at"),
            "error": info.get("error"),
        }

    def get_result(self, connection_id):
        """Get results of a single user extraction"""
        info = self._store.get(connection_id)
        if not info:
            return None
        current_status = info.get("status")
        user_upn = info.get("user_upn")
        
        if current_status == "completed":
            result = self.db.get_emails_by_user_upn(user_upn)  # Ensure emails are loaded
            return {
                "connection_id": connection_id,
                "user_upn": user_upn,
                "status": current_status,
                "result": result,
                "started_at": info.get("started_at"),
                "completed_at": info.get("completed_at"),
                "error": info.get("error")
            }
        
        return None

    def get_batch_status(self, batch_id):
        """Get status of a batch extraction"""
        info = self._store.get(batch_id)
        if not info:
            return {"status": "not_found"}
        
        return {
            "status": info.get("status", "unknown"),
            "started_at": info.get("started_at"),
            "completed_at": info.get("completed_at"),
            "error": info.get("error"),
            "total_users": len(info.get("users", [])),
            "processed_users": len(info.get("processed_users", [])),
            "failed_users": len(info.get("failed_users", [])),
            "remaining_users": len(info.get("users", [])) - len(info.get("processed_users", [])) - len(info.get("failed_users", []))
        }

    def get_batch_result(self, batch_id):
        """Get results of a batch extraction"""
        info = self._store.get(batch_id)
        if not info:
            return None
        
        if info.get("status") == "completed":
            return {
                "batch_id": batch_id,
                "processed_users": info.get("processed_users", []),
                "failed_users": info.get("failed_users", []),
                "started_at": info.get("started_at"),
                "completed_at": info.get("completed_at")
            }
        
        return None

    def pause_extraction(self, connection_id):
        """Pause an ongoing extraction task"""
        if connection_id in self._store:
            if self._store[connection_id]['status'] == 'in_progress':
                self.paused_tasks.add(connection_id)
                self._store[connection_id]['status'] = 'paused'
                self._save_store()
                
                # Create pause event if it doesn't exist
                if connection_id not in self.pause_events:
                    self.pause_events[connection_id] = threading.Event()
                self.pause_events[connection_id].clear()  # Set event to blocked state
                
                return True, "Extraction paused"
        return False, "Task not found or not running"

    def continue_extraction(self, connection_id):
        """Continue a paused extraction task"""
        if connection_id in self._store and self._store[connection_id].get('status') == 'paused':
            self.paused_tasks.discard(connection_id)
            self._store[connection_id]['status'] = 'in_progress'
            self._save_store()
            # Set the event to allow the thread to continue
            if connection_id in self.pause_events:
                self.pause_events[connection_id].set()
            return True, "Extraction continued"
        return False, "Task not found or not paused"

    def cancel_extraction(self, connection_id):
        """Cancel an extraction task"""
        if connection_id in self._store:
            self.cancelled_tasks.add(connection_id)
            self._store[connection_id]['status'] = 'cancelled'
            self._store[connection_id]['completed_at'] = time.time()
            self._save_store()
            
            # Stop the thread if it's still running
            if connection_id in self.active_threads:
                thread = self.active_threads[connection_id]
                if thread.is_alive():
                    # We can't directly kill the thread, but we can mark it for cleanup
                    del self.active_threads[connection_id]
            
            return True, "Extraction cancelled"
        return False, "Task not found"

    def pause_batch_extraction(self, batch_id):
        """Pause a batch extraction task"""
        if batch_id in self._store:
            if self._store[batch_id]['status'] == 'in_progress':
                self.paused_tasks.add(batch_id)
                self._store[batch_id]['status'] = 'paused'
                self._save_store()
                
                # Create pause event if it doesn't exist
                if batch_id not in self.pause_events:
                    self.pause_events[batch_id] = threading.Event()
                self.pause_events[batch_id].clear()  # Set event to blocked state
                
                return True, "Batch extraction paused"
        return False, "Batch not found or not running"

    def continue_batch_extraction(self, batch_id):
        """Continue a paused batch extraction task"""
        if batch_id in self._store and self._store[batch_id].get('status') == 'paused':
            self.paused_tasks.discard(batch_id)
            self._store[batch_id]['status'] = 'in_progress'
            self._save_store()
            # Set the event to allow the thread to continue
            if batch_id in self.pause_events:
                self.pause_events[batch_id].set()
            return True, "Batch extraction continued"
        return False, "Batch not found or not paused"

    def cancel_batch_extraction(self, batch_id):
        """Cancel a batch extraction task"""
        if batch_id in self._store:
            self.cancelled_tasks.add(batch_id)
            self._store[batch_id]['status'] = 'cancelled'
            self._store[batch_id]['completed_at'] = time.time()
            self._save_store()
            
            # Stop the thread if it's still running
            if batch_id in self.active_threads:
                thread = self.active_threads[batch_id]
                if thread.is_alive():
                    # We can't directly kill the thread, but we can mark it for cleanup
                    del self.active_threads[batch_id]
            
            return True, "Batch extraction cancelled"
        return False, "Batch not found" 
