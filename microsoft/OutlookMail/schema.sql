-- Email table to store the main email data
CREATE TABLE IF NOT EXISTS emails (
    id TEXT PRIMARY KEY,  -- Message ID from Microsoft Graph API
    user_upn TEXT NOT NULL,  -- User Principal Name (email address)
    subject TEXT,
    body TEXT,
    body_preview TEXT,
    importance TEXT,
    conversation_id TEXT,
    created_date_time TEXT,
    received_date_time TEXT,
    sent_date_time TEXT,
    has_attachments BOOLEAN,
    is_draft BOOLEAN,
    is_read BOOLEAN,
    parent_folder_id TEXT,
    folder_name TEXT,  -- 'inbox', 'sent', or 'both'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Table to store email recipients
CREATE TABLE IF NOT EXISTS email_recipients (
    recipient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id TEXT NOT NULL,  -- Foreign key to emails table
    recipient_type TEXT NOT NULL,  -- 'from', 'to', 'cc', 'bcc'
    email_address TEXT NOT NULL,
    name TEXT,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
);

-- Table to store email attachments
CREATE TABLE IF NOT EXISTS email_attachments (
    attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id TEXT NOT NULL,  -- Foreign key to emails table
    attachment_name TEXT NOT NULL,
    content_type TEXT,
    size INTEGER,
    content_url TEXT,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
);

-- Table to store skipped emails
CREATE TABLE IF NOT EXISTS skipped_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_upn TEXT NOT NULL,
    message_id TEXT NOT NULL,
    from_address TEXT,
    subject TEXT,
    reason TEXT NOT NULL,
    logged_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Table to store users with no more emails
CREATE TABLE IF NOT EXISTS no_more_emails (
    user_upn TEXT PRIMARY KEY,
    added_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_emails_user_upn ON emails(user_upn);
CREATE INDEX IF NOT EXISTS idx_emails_folder_name ON emails(folder_name);
CREATE INDEX IF NOT EXISTS idx_email_recipients_email_id ON email_recipients(email_id);
CREATE INDEX IF NOT EXISTS idx_email_attachments_email_id ON email_attachments(email_id);
CREATE INDEX IF NOT EXISTS idx_skipped_emails_user_upn ON skipped_emails(user_upn); 