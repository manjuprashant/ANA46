import threading
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
from model import (
    get_extraction,
    save_extraction,
    save_calendar_events,
    get_events_by_connection_id,
    get_next_link,
    save_next_link,
    clear_all_next_links,
)

def html_to_text(html_content):
    """Convert HTML to clean plain text."""
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator="\n")

    text = re.sub(r"[_]{5,}", "", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    text = re.sub(r"\s{2,}", " ", text.strip())

    return text.strip()

class MicrosoftCalendarExtractionService:
    def start_extraction(self, connection_id, config_payload):
        existing = get_extraction(connection_id)
        if existing:
            if existing.status == 'in_progress':
                return False, "Extraction already in progress"
            elif existing.status == 'completed':
                return False, "Extraction already completed"
            elif existing.status == 'failed':
                # Allow retry on failed
                pass

        
        save_extraction(
            connection_id=connection_id,
            status='in_progress',
            config=config_payload,
            error=None,
            started_at=datetime.utcnow(),
            completed_at=None
        )

        thread = threading.Thread(
            target=self._extract_calendar_events,
            args=(connection_id,)
        )
        thread.start()

        return True, "Calendar extraction started"

    def _extract_calendar_events(self, connection_id):
        try:
            extraction = get_extraction(connection_id)
            config = extraction.config

            token = self._get_access_token(
                tenant_id=config['tenant_id'],
                client_id=config['client_id'],
                client_secret=config['client_secret'],
                scopes=["https://graph.microsoft.com/.default"]
            )

            user_upns = config.get('user_upns', [])

            for user_principal_name in user_upns:
                calendars = self._get_user_calendars(token, user_principal_name)

                for calendar in calendars:
                    calendar_id = calendar['id']
                    events_url = f"https://graph.microsoft.com/v1.0/users/{user_principal_name}/calendars/{calendar_id}/events?$filter=start/dateTime ge '2024-01-01T00:00:00.0000000'"

                    while events_url:
                        headers = {
                            'Authorization': f'Bearer {token}',
                            'Content-Type': 'application/json'
                        }
                        res = requests.get(events_url, headers=headers)
                        res.raise_for_status()
                        data = res.json()
                        raw_events = data.get('value', [])
                        print(f"{len(raw_events)} events found")
                        # Parse and prepare events for saving
                        events_to_save = []
                        for event in raw_events:
                            try:
                                location = event.get("location", {}).get("displayName", "").strip()
                                description = html_to_text(event.get("bodyPreview", "No description"))
                                virtual = event.get("isOnlineMeeting", False)

                                meeting_links = [
                                    "zoom.us", "google.com", "meet.google", "teams.microsoft",
                                    "interview-links.indeed", "employers.indeed.com", "virtual-interviews/upcoming"
                                ]
                                if any(link in location.lower() for link in meeting_links) or \
                                any(link in description.lower() for link in meeting_links):
                                    virtual = True

                                if not location or location.lower() == "virtual meeting (link in description)":
                                    location = "Virtual Meeting (link in Description)"

                                raw_attendees = event.get("attendees", [])
                                attendees = []
                                if raw_attendees:
                                    for att in raw_attendees:
                                        addr = att["emailAddress"]
                                        attendees.append({
                                            "name": addr.get("name"),
                                            "email": addr.get("address"),
                                            "type": att.get("type", "Required"),
                                            "response": att.get("status", {}).get("response"),
                                            "proposed_time": att.get("proposedNewTime")
                                        })
                                else:
                                    org_addr = event["organizer"]["emailAddress"]
                                    attendees = [{
                                        "name": org_addr.get("name"),
                                        "email": org_addr.get("address"),
                                        "type": "Organizer",
                                        "response": event.get("responseStatus", {}).get("response"),
                                        "proposed_time": None
                                    }]

                                org = event["organizer"]["emailAddress"]
                                events_to_save.append({
                                    "event_id": event["id"],
                                    "connection_id": connection_id,
                                    "tenant_id": config['tenant_id'],
                                    "organizer_name": org.get("name"),
                                    "organizer_email": org.get("address"),
                                    "title": event.get("subject", "No title"),
                                    "description": description,
                                    "location": location,
                                    "virtual": virtual,
                                    "start_time": datetime.fromisoformat(event["start"]["dateTime"]),
                                    "end_time": datetime.fromisoformat(event["end"]["dateTime"]),
                                    "organizer_response": event.get("responseStatus", {}).get("response"),
                                    "allow_new_time_proposals": event.get("allowNewTimeProposals", False),
                                    "attendees": attendees,
                                    "date_extracted": datetime.utcnow()
                                })

                            except Exception as parse_err:
                                print(f"Failed to parse event for {user_principal_name}: {parse_err}")

                        # Save events fetched on this page **immediately**
                        save_calendar_events(connection_id, events_to_save)

                        # Save or update the next link in DB for this user
                        next_link = data.get('@odata.nextLink')
                        save_next_link(connection_id, user_principal_name, next_link)

                        if next_link:
                            events_url = next_link
                        else:
                            events_url = None

            # After all user calendars done, mark extraction complete and clear all next links
            save_extraction(
                connection_id=connection_id,
                status='completed',
                config=config,
                error=None,
                started_at=extraction.started_at,
                completed_at=datetime.utcnow()
            )
            clear_all_next_links(connection_id)  # remove all saved next links after successful full extraction

        except Exception as e:
            print(f"Error during extraction: {e}")
            extraction = get_extraction(connection_id)
            save_extraction(
                connection_id=connection_id,
                status='failed',
                config=extraction.config if extraction else None,
                error=str(e),
                started_at=extraction.started_at if extraction else datetime.utcnow(),
                completed_at=datetime.utcnow()
            )



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

    def _get_user_calendars(self, token, user_principal_name):
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        url = f'https://graph.microsoft.com/v1.0/users/{user_principal_name}/calendars'
        calendars = []

        while url:
            res = requests.get(url, headers=headers)
            res.raise_for_status()
            data = res.json()
            calendars.extend(data.get('value', []))
            url = data.get('@odata.nextLink')

        return calendars

    def get_status(self, connection_id):
        info = get_extraction(connection_id)
        if not info:
            return {"status": "not_started"}

        return {
            "status": info.status,
            "started_at": info.started_at,
            "completed_at": info.completed_at,
            "error": info.error,
        }

    def get_result(self, connection_id):
        extraction = get_extraction(connection_id)
        # if not extraction or extraction.status != "completed":
        #     return None

        events = get_events_by_connection_id(connection_id)
        return [event.to_dict() for event in events]
