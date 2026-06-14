"""Google Calendar API client.

Read-only access to fetch today's events. Supports multiple calendars
(e.g. work + personal). Used for context-aware nudges.
"""

import time
import logging
from datetime import date, datetime, timedelta
from typing import Optional

import requests

from app.models import db, User, CalendarEvent

logger = logging.getLogger(__name__)

API_BASE = "https://www.googleapis.com/calendar/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"


class GoogleCalendarError(Exception):
    pass


class GoogleCalendarClient:
    """Read-only Google Calendar wrapper."""

    def __init__(self, app_config, user_id: int = 1):
        self._config_client_id = app_config.get("GOOGLE_CLIENT_ID", "")
        self._config_client_secret = app_config.get("GOOGLE_CLIENT_SECRET", "")
        self.user_id = user_id

    def _get_user(self) -> User:
        user = db.session.get(User, self.user_id)
        if not user:
            raise GoogleCalendarError("No user found")
        return user

    @property
    def client_id(self):
        user = self._get_user()
        return user.google_client_id or self._config_client_id

    @property
    def client_secret(self):
        user = self._get_user()
        return user.google_client_secret or self._config_client_secret

    def _get_valid_token(self) -> str:
        """Get a valid access token, refreshing if needed."""
        user = self._get_user()

        if not user.google_access_token:
            raise GoogleCalendarError("Google Calendar not connected. Go to Settings.")

        # Refresh if expiring within 5 minutes
        if user.google_token_expires_at and user.google_token_expires_at < time.time() + 300:
            self._refresh_token(user)

        return user.google_access_token

    def _refresh_token(self, user: User):
        """Refresh the Google access token."""
        if not user.google_refresh_token:
            raise GoogleCalendarError("No refresh token. Re-connect Google Calendar.")

        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": user.google_refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )

        if resp.status_code != 200:
            logger.error(f"Google token refresh failed: {resp.status_code}")
            raise GoogleCalendarError(f"Token refresh failed: {resp.status_code}")

        data = resp.json()
        user.google_access_token = data["access_token"]
        user.google_token_expires_at = time.time() + data.get("expires_in", 3600)
        # Google doesn't always return a new refresh token
        if "refresh_token" in data:
            user.google_refresh_token = data["refresh_token"]
        db.session.commit()
        logger.info("Google token refreshed")

    def _api_get(self, path: str, params: dict = None) -> dict:
        """Make an authenticated GET request to the Calendar API."""
        token = self._get_valid_token()
        resp = requests.get(
            f"{API_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
            timeout=30,
        )

        if resp.status_code == 401:
            raise GoogleCalendarError("Unauthorized — token may be expired")
        if resp.status_code != 200:
            logger.error(f"Google Calendar API error {resp.status_code}: {resp.text[:500]}")
            return {}

        return resp.json()

    def list_calendars(self) -> list:
        """List all calendars the user has access to."""
        data = self._api_get("/users/me/calendarList")
        calendars = []
        for item in data.get("items", []):
            calendars.append({
                "id": item["id"],
                "name": item.get("summary", "Untitled"),
                "primary": item.get("primary", False),
                "color": item.get("backgroundColor", "#3d6b4f"),
            })
        return calendars

    def fetch_events(self, calendar_id: str, target_date: date) -> list:
        """Fetch events for a single calendar on a given date."""
        # Use timezone-aware boundaries to avoid missing events at day boundaries
        # Helsinki is UTC+2 (winter) or UTC+3 (summer), so pad by a few hours
        user = self._get_user()
        tz = user.timezone or "Europe/Helsinki"

        start = f"{target_date.isoformat()}T00:00:00"
        end = f"{(target_date + timedelta(days=1)).isoformat()}T00:00:00"

        data = self._api_get(
            f"/calendars/{requests.utils.quote(calendar_id, safe='')}/events",
            params={
                "timeMin": start,
                "timeMax": end,
                "timeZone": tz,
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 50,
            },
        )

        events = []
        for item in data.get("items", []):
            if item.get("status") == "cancelled":
                continue

            start_info = item.get("start", {})
            end_info = item.get("end", {})

            is_all_day = "date" in start_info
            start_time = None
            end_time = None

            if not is_all_day:
                # Parse datetime like "2024-01-15T09:00:00+02:00"
                start_dt = start_info.get("dateTime", "")
                end_dt = end_info.get("dateTime", "")
                if "T" in start_dt:
                    start_time = start_dt.split("T")[1][:5]
                if "T" in end_dt:
                    end_time = end_dt.split("T")[1][:5]

            events.append({
                "event_id": item.get("id", ""),
                "summary": item.get("summary", "(No title)"),
                "start_time": start_time,
                "end_time": end_time,
                "is_all_day": is_all_day,
            })

        return events

    def sync_events(self, target_date: date) -> list:
        """Sync events from all selected calendars for a date. Returns event list."""
        user = self._get_user()
        calendar_ids_str = user.google_calendar_ids or ""
        calendar_ids = [c.strip() for c in calendar_ids_str.split(",") if c.strip()]

        if not calendar_ids:
            # If no specific calendars selected, use primary
            calendar_ids = ["primary"]

        # Clear old events for this date
        CalendarEvent.query.filter_by(
            user_id=self.user_id,
            date=target_date,
        ).delete()

        all_events = []
        for cal_id in calendar_ids:
            try:
                events = self.fetch_events(cal_id, target_date)
                # Determine a friendly calendar name
                cal_name = "Work" if "work" in cal_id.lower() else "Personal"
                if cal_id == "primary":
                    cal_name = "Primary"

                for e in events:
                    record = CalendarEvent(
                        user_id=self.user_id,
                        calendar_id=cal_id,
                        calendar_name=cal_name,
                        event_id=e["event_id"],
                        date=target_date,
                        start_time=e["start_time"],
                        end_time=e["end_time"],
                        summary=e["summary"],
                        is_all_day=e["is_all_day"],
                    )
                    db.session.add(record)
                    all_events.append(record)

            except Exception as ex:
                logger.error(f"Error syncing calendar {cal_id}: {ex}")

        db.session.commit()
        logger.info(f"Synced {len(all_events)} events for {target_date}")
        return all_events


def analyze_day(user_id: int, target_date: date) -> dict:
    """Analyze a day's calendar for nudge-relevant signals.

    Returns a dict with:
      - total_meetings: count of non-all-day events
      - busy_hours: estimated hours in meetings
      - first_meeting: start time of first event
      - last_meeting: end time of last event
      - free_gaps: list of gaps >= 30 min between meetings
      - is_busy_day: True if 4+ meetings or 5+ hours booked
      - is_light_day: True if <= 1 meeting
      - lunch_free: True if 11:30-13:00 has no events
    """
    events = CalendarEvent.query.filter(
        CalendarEvent.user_id == user_id,
        CalendarEvent.date == target_date,
        CalendarEvent.is_all_day == False,
    ).order_by(CalendarEvent.start_time).all()

    if not events:
        return {
            "total_meetings": 0,
            "busy_hours": 0,
            "first_meeting": None,
            "last_meeting": None,
            "free_gaps": [],
            "is_busy_day": False,
            "is_light_day": True,
            "lunch_free": True,
        }

    total = len(events)
    busy_mins = 0
    for e in events:
        if e.start_time and e.end_time:
            try:
                sh, sm = map(int, e.start_time.split(":"))
                eh, em = map(int, e.end_time.split(":"))
                busy_mins += (eh * 60 + em) - (sh * 60 + sm)
            except (ValueError, AttributeError):
                busy_mins += 60  # Assume 1 hour if can't parse

    busy_hours = round(busy_mins / 60, 1)

    # Find gaps >= 30 min
    free_gaps = []
    for i in range(len(events) - 1):
        if events[i].end_time and events[i + 1].start_time:
            try:
                eh, em = map(int, events[i].end_time.split(":"))
                sh, sm = map(int, events[i + 1].start_time.split(":"))
                gap = (sh * 60 + sm) - (eh * 60 + em)
                if gap >= 30:
                    free_gaps.append({
                        "start": events[i].end_time,
                        "end": events[i + 1].start_time,
                        "duration_mins": gap,
                    })
            except (ValueError, AttributeError):
                pass

    # Check if lunch window (11:30–13:00) is free
    lunch_free = True
    for e in events:
        if e.start_time and e.end_time:
            try:
                sh, sm = map(int, e.start_time.split(":"))
                eh, em = map(int, e.end_time.split(":"))
                start_m = sh * 60 + sm
                end_m = eh * 60 + em
                # Overlaps with 11:30-13:00?
                if start_m < 780 and end_m > 690:  # 780=13:00, 690=11:30
                    lunch_free = False
                    break
            except (ValueError, AttributeError):
                pass

    return {
        "total_meetings": total,
        "busy_hours": busy_hours,
        "first_meeting": events[0].start_time,
        "last_meeting": events[-1].end_time,
        "free_gaps": free_gaps,
        "is_busy_day": total >= 4 or busy_hours >= 5,
        "is_light_day": total <= 1,
        "lunch_free": lunch_free,
    }
