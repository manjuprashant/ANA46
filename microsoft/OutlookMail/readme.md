# OutlookMail Extraction Module

This module provides a service and API for extracting emails from Microsoft Outlook mailboxes using the Microsoft Graph API. It supports single-user and batch extraction, as well as pausing, continuing, and cancelling extraction tasks.

## Features
- Extract emails for a single user or a batch of users
- Save emails to a database (SQLite/Postgres)
- Pause, continue, and cancel extraction tasks (single and batch)
- Track extraction status and results
- Robust error handling and logging

## Configuration
You can provide configuration values (tenant ID, client ID, client secret) in the request body for each extraction, or set them as environment variables:

```
OUTLOOK_CLIENT_ID=your_client_id
OUTLOOK_CLIENT_SECRET=your_client_secret
TENANT_ID=your_tenant_id
```

## Running the Flask API

```
cd extractions/microsoft/OutlookMail
python app.py
```

The API will be available at `http://localhost:3006` by default.

---

## Flask API Endpoints

### Single User Extraction
- **Start Extraction:**
  - `POST /api/emails/extract/start/<connection_id>`
  - **Body:**
    ```json
    {
      "user_upn": "user@example.com",
      "config": {
        "tenant_id": "your_tenant_id",
        "outlook_client_id": "your_client_id",
        "outlook_client_secret": "your_client_secret"
      }
    }
    ```
- **Pause Extraction:**
  - `POST /api/emails/extract/pause/<connection_id>`
- **Continue Extraction:**
  - `POST /api/emails/extract/continue/<connection_id>`
- **Cancel Extraction:**
  - `POST /api/emails/extract/cancel/<connection_id>`
- **Check Status:**
  - `GET /api/emails/extract/status/<connection_id>`
- **Get Result:**
  - `GET /api/emails/extract/result/<connection_id>`

### Batch Extraction
- **Start Batch Extraction:**
  - `POST /api/emails/extract/batch/start`
  - **Body:**
    ```json
    {
      "user_upns": ["user1@example.com", "user2@example.com"],
      "config": {
        "tenant_id": "your_tenant_id",
        "outlook_client_id": "your_client_id",
        "outlook_client_secret": "your_client_secret"
      }
    }
    ```
- **Pause Batch Extraction:**
  - `POST /api/emails/extract/batch/pause/<batch_id>`
- **Continue Batch Extraction:**
  - `POST /api/emails/extract/batch/continue/<batch_id>`
- **Cancel Batch Extraction:**
  - `POST /api/emails/extract/batch/cancel/<batch_id>`
- **Check Batch Status:**
  - `GET /api/emails/extract/batch/status/<batch_id>`
- **Get Batch Result:**
  - `GET /api/emails/extract/batch/result/<batch_id>`

---

## How to Use Pause, Continue, and Cancel

- **Pause**: Temporarily stops the extraction process at a safe checkpoint. The extraction can be resumed later from where it left off. Use the pause endpoint for either a single extraction or a batch extraction.
- **Continue**: Resumes a previously paused extraction. The extraction will pick up from the last processed message or user.
- **Cancel**: Stops the extraction process and marks it as cancelled. Cancelled extractions cannot be resumed. Any emails processed before cancellation are saved.

**Typical Workflow:**
1. Start an extraction (single or batch).
2. If you need to temporarily stop, call the pause endpoint.
3. To resume, call the continue endpoint.
4. To stop and not resume, call the cancel endpoint.

---

## Example cURL Commands

**Start Single Extraction:**
```sh
curl -X POST http://localhost:3006/api/emails/extract/start/conn1 \
  -H "Content-Type: application/json" \
  -d '{
    "user_upn": "user@example.com",
    "config": {
      "tenant_id": "your_tenant_id",
      "outlook_client_id": "your_client_id",
      "outlook_client_secret": "your_client_secret"
    }
  }'
```

**Start Batch Extraction:**
```sh
curl -X POST http://localhost:3006/api/emails/extract/batch/start \
  -H "Content-Type: application/json" \
  -d '{
    "user_upns": ["user1@example.com", "user2@example.com", ...],
    "config": {
      "tenant_id": "your_tenant_id",
      "outlook_client_id": "your_client_id",
      "outlook_client_secret": "your_client_secret"
    }
  }'
```

**Pause Batch Extraction:**
```sh
curl -X POST http://localhost:3006/api/emails/extract/batch/pause/batch_1234567890
```

**Continue Batch Extraction:**
```sh
curl -X POST http://localhost:3006/api/emails/extract/batch/continue/batch_1234567890
```

**Cancel Batch Extraction:**
```sh
curl -X POST http://localhost:3006/api/emails/extract/batch/cancel/batch_1234567890
```

---

## Status and Results
- Status endpoints return the current state (`in_progress`, `paused`, `completed`, `cancelled`, etc.) and progress information.
- Result endpoints return the extracted emails or batch summary if completed.

## Notes
- Pausing and continuing works even after a server restart, as long as the store file is preserved. Using the batch_id to track the tasks.
- Cancelled or completed tasks cannot be resumed.
- All configuration values can be provided in the request body or will be taken from environment variables if omitted.

For more details, see the code and comments in `services.py` and `app.py`.
