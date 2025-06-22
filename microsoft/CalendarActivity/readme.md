Here’s a complete and clean **`README.md`** for your Microsoft Calendar Extraction microservice using Flask, SQLAlchemy, and Microsoft Graph API:

---

# 📆 Microsoft Calendar Extraction Service

A Python-based API service to extract calendar events from Microsoft 365 using Microsoft Graph API, with data stored in a local SQLite database.

---

## 🚀 Features

* Start calendar extraction for a user or multiple users
* Fetch extraction status
* Retrieve extracted calendar events
* Asynchronous processing using background threads
* SQLAlchemy ORM with SQLite (easily swappable with PostgreSQL/MySQL)
* CORS enabled for frontend integration

---

## 📦 Requirements

* Python 3.7+
* Microsoft 365 Tenant (Azure App Registration)
* Microsoft Graph API access

---

## 🔧 Installation

```bash
git clone https://github.com/your-org/calendar-extraction-service.git
cd calendar-extraction-service

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

---

## ⚙️ Configuration

Create an Azure App Registration and provide the following:

* `tenant_id`
* `client_id`
* `client_secret`
* Delegated users' UPNs (emails)

Ensure the app has **Calendars.Read** permission.

---

## ▶️ Running the Server

```bash
python app.py
```

Default port: `3005`

---

## 🧪 API Usage

### 1. **Start Extraction**

```
POST /api/calendar/start/<connection_id>
```

**Request JSON:**

```json
{
  "tenant_id": "YOUR_TENANT_ID",
  "client_id": "YOUR_CLIENT_ID",
  "client_secret": "YOUR_CLIENT_SECRET",
  "user_upns": [
    "user1@yourdomain.com",
    "user2@yourdomain.com"
  ]
}
```

**Response**

```json
{
  "message": "Calendar extraction started",
  "connection_id": "test-conn-123"
}
```

---

### 2. **Check Status**

```
GET /api/calendar/status/<connection_id>
```

**Response:**

```json
{
  "status": "completed",
  "started_at": 1717583420.511,
  "completed_at": 1717583435.342,
  "error": null
}
```

---

### 3. **Get Result**

```
GET /api/calendar/result/<connection_id>
```

**Response:**

```json
{
  "connection_id": "test-conn-123",
  "users": {
    "user1@yourdomain.com": {
      "Work Calendar": [ ...events... ]
    }
  }
}
```

---

## 📁 Project Structure

```
.
├── app.py                      # Flask app and endpoints
├── model.py                    # SQLAlchemy model and DB logic
├── services.py                 # Microsoft Graph extraction logic
├── requirements.txt
└── README.md
```

---

## 🧹 Cleanup

To reset the DB (for testing):

```bash
rm calendar_extraction.db
python -c "from model import init_db; init_db()"
```

---

## 🛡️ Security Note

* Keep `client_secret` safe (do not log or expose).
* Use HTTPS in production.
* Consider storing secrets using environment variables or a secure vault.

---

## 📜 License

MIT License – use freely with attribution.

---

Let me know if you'd like a Dockerfile or deployment instructions (Heroku, Render, AWS, etc.).
