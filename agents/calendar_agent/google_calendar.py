"""Google Calendar API client."""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CalendarEvent:
    """Calendar event."""

    id: str
    title: str
    description: str | None
    start: datetime
    end: datetime
    location: str | None
    attendees: list[str]
    is_all_day: bool
    status: str  # confirmed, tentative, cancelled
    html_link: str | None


class GoogleCalendarClient:
    """Client for Google Calendar API.

    Note: This is a simplified implementation.
    In production, use google-api-python-client with proper OAuth2.
    """

    def __init__(self, credentials_path: str | None = None):
        self.credentials_path = credentials_path or os.getenv(
            "GOOGLE_CREDENTIALS_PATH", ""
        )
        self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        self._service = None

    def _get_service(self):
        """Get Google Calendar service.

        This is a placeholder - implement with actual Google API client.
        """
        if self._service is None:
            # In production, initialize with:
            # from google.oauth2.credentials import Credentials
            # from googleapiclient.discovery import build
            # creds = Credentials.from_authorized_user_file(self.credentials_path)
            # self._service = build('calendar', 'v3', credentials=creds)
            logger.warning("Google Calendar API not configured")
        return self._service

    def list_events(
        self,
        time_min: datetime | None = None,
        time_max: datetime | None = None,
        max_results: int = 10,
    ) -> list[CalendarEvent]:
        """List upcoming calendar events."""
        service = self._get_service()
        if not service:
            logger.warning("Calendar service not available")
            return []

        try:
            events_result = service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min.isoformat() + "Z" if time_min else None,
                timeMax=time_max.isoformat() + "Z" if time_max else None,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            events = events_result.get("items", [])
            return [self._parse_event(e) for e in events]
        except Exception as e:
            logger.error(f"Failed to list events: {e}")
            return []

    def get_event(self, event_id: str) -> CalendarEvent | None:
        """Get a specific calendar event."""
        service = self._get_service()
        if not service:
            return None

        try:
            event = service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id,
            ).execute()
            return self._parse_event(event)
        except Exception as e:
            logger.error(f"Failed to get event: {e}")
            return None

    def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        description: str | None = None,
        location: str | None = None,
        attendees: list[str] | None = None,
    ) -> CalendarEvent | None:
        """Create a new calendar event."""
        service = self._get_service()
        if not service:
            return None

        event_body = {
            "summary": title,
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
        }

        if description:
            event_body["description"] = description
        if location:
            event_body["location"] = location
        if attendees:
            event_body["attendees"] = [{"email": a} for a in attendees]

        try:
            event = service.events().insert(
                calendarId=self.calendar_id,
                body=event_body,
            ).execute()
            return self._parse_event(event)
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            return None

    def update_event(
        self,
        event_id: str,
        title: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        description: str | None = None,
        location: str | None = None,
    ) -> CalendarEvent | None:
        """Update an existing calendar event."""
        service = self._get_service()
        if not service:
            return None

        try:
            # Get existing event
            event = service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id,
            ).execute()

            # Update fields
            if title:
                event["summary"] = title
            if description:
                event["description"] = description
            if location:
                event["location"] = location
            if start:
                event["start"] = {"dateTime": start.isoformat(), "timeZone": "UTC"}
            if end:
                event["end"] = {"dateTime": end.isoformat(), "timeZone": "UTC"}

            updated = service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event,
            ).execute()
            return self._parse_event(updated)
        except Exception as e:
            logger.error(f"Failed to update event: {e}")
            return None

    def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event."""
        service = self._get_service()
        if not service:
            return False

        try:
            service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id,
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete event: {e}")
            return False

    def _parse_event(self, event: dict[str, Any]) -> CalendarEvent:
        """Parse a Google Calendar event."""
        start_data = event.get("start", {})
        end_data = event.get("end", {})

        # Check if all-day event
        is_all_day = "date" in start_data

        if is_all_day:
            start = datetime.fromisoformat(start_data["date"])
            end = datetime.fromisoformat(end_data["date"])
        else:
            start = datetime.fromisoformat(
                start_data.get("dateTime", "").replace("Z", "+00:00")
            )
            end = datetime.fromisoformat(
                end_data.get("dateTime", "").replace("Z", "+00:00")
            )

        attendees = [
            a.get("email", "") for a in event.get("attendees", [])
        ]

        return CalendarEvent(
            id=event.get("id", ""),
            title=event.get("summary", ""),
            description=event.get("description"),
            start=start,
            end=end,
            location=event.get("location"),
            attendees=attendees,
            is_all_day=is_all_day,
            status=event.get("status", "confirmed"),
            html_link=event.get("htmlLink"),
        )
