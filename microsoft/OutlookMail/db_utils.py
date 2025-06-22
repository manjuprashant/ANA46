import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any


class EmailDB:
    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(current_dir, "emails.db")

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # ✅ makes rows behave like dicts
        return conn

    def save_email(self, email_data: Dict[str, Any], user_upn: str, folder_name: str):
        """Save an email and its related data to the database."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Insert main email data
            cursor.execute(
                """
                INSERT OR REPLACE INTO emails (
                    id, user_upn, subject, body, body_preview, importance,
                    conversation_id, created_date_time, received_date_time,
                    sent_date_time, has_attachments, is_draft, is_read,
                    parent_folder_id, folder_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    email_data["id"],
                    user_upn,
                    email_data.get("subject"),
                    email_data.get("body", {}).get("content"),
                    email_data.get("bodyPreview"),
                    email_data.get("importance"),
                    email_data.get("conversationId"),
                    email_data.get("createdDateTime"),
                    email_data.get("receivedDateTime"),
                    email_data.get("sentDateTime"),
                    email_data.get("hasAttachments", False),
                    email_data.get("isDraft", False),
                    email_data.get("isRead", False),
                    email_data.get("parentFolderId"),
                    folder_name,
                ),
            )

            # Save recipients
            self._save_recipients(cursor, email_data["id"], email_data)

            # Save attachments if any
            if email_data.get("hasAttachments"):
                self._save_attachments(
                    cursor, email_data["id"], email_data.get("attachments", [])
                )

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _save_recipients(self, cursor, email_id: str, email_data: Dict[str, Any]):
        """Save email recipients (from, to, cc, bcc)."""
        # Save from recipient
        if "from" in email_data:
            from_data = email_data["from"]
            cursor.execute(
                """
                INSERT INTO email_recipients (email_id, recipient_type, email_address, name)
                VALUES (?, 'from', ?, ?)
            """,
                (
                    email_id,
                    from_data.get("emailAddress", {}).get("address"),
                    from_data.get("emailAddress", {}).get("name"),
                ),
            )

        # Save to recipients
        for recipient in email_data.get("toRecipients", []):
            cursor.execute(
                """
                INSERT INTO email_recipients (email_id, recipient_type, email_address, name)
                VALUES (?, 'to', ?, ?)
            """,
                (
                    email_id,
                    recipient.get("emailAddress", {}).get("address"),
                    recipient.get("emailAddress", {}).get("name"),
                ),
            )

        # Save cc recipients
        for recipient in email_data.get("ccRecipients", []):
            cursor.execute(
                """
                INSERT INTO email_recipients (email_id, recipient_type, email_address, name)
                VALUES (?, 'cc', ?, ?)
            """,
                (
                    email_id,
                    recipient.get("emailAddress", {}).get("address"),
                    recipient.get("emailAddress", {}).get("name"),
                ),
            )

        # Save bcc recipients
        for recipient in email_data.get("bccRecipients", []):
            cursor.execute(
                """
                INSERT INTO email_recipients (email_id, recipient_type, email_address, name)
                VALUES (?, 'bcc', ?, ?)
            """,
                (
                    email_id,
                    recipient.get("emailAddress", {}).get("address"),
                    recipient.get("emailAddress", {}).get("name"),
                ),
            )

    def _save_attachments(
        self, cursor, email_id: str, attachments: List[Dict[str, Any]]
    ):
        """Save email attachments."""
        for attachment in attachments:
            cursor.execute(
                """
                INSERT INTO email_attachments (
                    email_id, attachment_name, content_type, size, content_url
                ) VALUES (?, ?, ?, ?, ?)
            """,
                (
                    email_id,
                    attachment.get("name"),
                    attachment.get("contentType"),
                    attachment.get("size"),
                    attachment.get("contentUrl"),
                ),
            )

    def save_skipped_email(
        self,
        user_upn: str,
        message_id: str,
        from_address: str,
        subject: str,
        reason: str,
    ):
        """Save information about a skipped email."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO skipped_emails (
                    user_upn, message_id, from_address, subject, reason
                ) VALUES (?, ?, ?, ?, ?)
            """,
                (user_upn, message_id, from_address, subject, reason),
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_existing_message_ids(self, user_upn: str) -> set:
        """Get set of existing message IDs for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT id FROM emails WHERE user_upn = ?
            """,
                (user_upn,),
            )
            return {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()

    def get_skipped_message_ids(self, user_upn: str) -> set:
        """Get set of skipped message IDs for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT message_id FROM skipped_emails WHERE user_upn = ?
            """,
                (user_upn,),
            )
            return {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()

    def get_processed_users(self) -> set:
        """Get set of processed users."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT DISTINCT user_upn FROM emails
            """
            )
            return {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()

    def get_no_more_emails_users(self) -> set:
        """Get set of users with no more emails."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT user_upn FROM no_more_emails
            """
            )
            return {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()

    def add_no_more_emails_user(self, user_upn: str):
        """Add a user to the no_more_emails list."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO no_more_emails (user_upn, added_at)
                VALUES (?, CURRENT_TIMESTAMP)
            """,
                (user_upn,),
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def is_user_in_no_more_emails(self, user_upn: str) -> bool:
        """Check if a user is in the no_more_emails list."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT 1 FROM no_more_emails WHERE user_upn = ?
            """,
                (user_upn,),
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def get_emails_by_user_upn(
        self,
        user_upn: str,
        limit: int = None,
        offset: int = None,
        folder_name: str = None,
        is_read: bool = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves extracted emails for a given user UPN directly from the database,
        including their recipients and attachments.

        This function performs multiple queries to efficiently reconstruct the
        full email object with its nested data.

        Args:
            user_upn (str): The User Principal Name (email address) of the user.
            limit (int, optional): Maximum number of emails to return. Defaults to None.
            offset (int, optional): Number of emails to skip. Defaults to None.
            folder_name (str, optional): Filter by 'inbox', 'sent', or 'both'. Defaults to None.
            is_read (bool, optional): Filter by read status (True for read, False for unread).
                                       Defaults to None (no filter).

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dictionary
                                   represents an email with its details, recipients, and attachments.
                                   Returns an empty list if no emails are found or an error occurs.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        print(user_upn)

        # Use a dictionary to build up email objects, keying by email ID
        emails_dict = {}

        try:
            # 1. Fetch main email data based on user_upn and optional filters
            email_query = """
                SELECT
                    id, user_upn, subject, body, body_preview, importance,
                    conversation_id, created_date_time, received_date_time,
                    sent_date_time, has_attachments, is_draft, is_read,
                    parent_folder_id, folder_name
                FROM
                    emails
                WHERE
                    user_upn = ?
            """
            params = [user_upn]

            if folder_name:
                email_query += " AND folder_name = ?"
                params.append(folder_name)
            if is_read is not None:
                # SQLite stores booleans as 0 or 1
                email_query += " AND is_read = ?"
                params.append(1 if is_read else 0)

            # Order by received date for chronological results, newest first
            email_query += " ORDER BY received_date_time DESC"

            if limit:
                email_query += " LIMIT ?"
                params.append(limit)
            if offset:
                email_query += " OFFSET ?"
                params.append(offset)

            cursor.execute(email_query, params)

            # Populate the emails_dict with basic email info
            for row in cursor.fetchall():
                email_id = row["id"]
                # Convert sqlite3.Row object to a standard dictionary
                email_entry = dict(row)

                # SQLite stores BOOLEAN as 0 or 1, convert back to Python bool
                email_entry["has_attachments"] = bool(email_entry["has_attachments"])
                email_entry["is_draft"] = bool(email_entry["is_draft"])
                email_entry["is_read"] = bool(email_entry["is_read"])

                # Initialize lists for nested data
                email_entry["recipients"] = []
                email_entry["attachments"] = []
                emails_dict[email_id] = email_entry

            # If no emails were found, we can return early
            if not emails_dict:
                return []

            # 2. Fetch recipients for all the email IDs we just retrieved
            email_ids_to_fetch = tuple(emails_dict.keys())
            # Create a string of question marks for the IN clause (?, ?, ?)
            placeholders = ",".join("?" * len(email_ids_to_fetch))

            recipients_query = f"""
                SELECT email_id, recipient_type, email_address, name
                FROM email_recipients
                WHERE email_id IN ({placeholders})
            """
            cursor.execute(recipients_query, email_ids_to_fetch)
            for row in cursor.fetchall():
                email_id = row["email_id"]
                # Append recipient info to the correct email in emails_dict
                if email_id in emails_dict:
                    emails_dict[email_id]["recipients"].append(dict(row))

            # 3. Fetch attachments for all the email IDs (if any)
            attachments_query = f"""
                SELECT email_id, attachment_name, content_type, size, content_url
                FROM email_attachments
                WHERE email_id IN ({placeholders})
            """
            cursor.execute(attachments_query, email_ids_to_fetch)
            for row in cursor.fetchall():
                email_id = row["email_id"]
                # Append attachment info to the correct email in emails_dict
                if email_id in emails_dict:
                    emails_dict[email_id]["attachments"].append(dict(row))

            # Convert the dictionary of reconstructed emails back into a list.
            # We iterate over the original `email_ids_to_fetch` to preserve the order
            # established by the initial `ORDER BY received_date_time DESC` clause.
            ordered_emails = [emails_dict[email_id] for email_id in email_ids_to_fetch]
            return ordered_emails

        except Exception as e:
            # In a real application, you'd use a logging system here instead of print
            print(f"Error retrieving emails for {user_upn}: {e}")
            return []  # Return an empty list to indicate failure or no results
        finally:
            conn.close()
