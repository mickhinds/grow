"""Oura API v2 client.

Handles OAuth2 token management and data fetching.
All methods return plain dicts — no Oura-specific objects leak out.
"""

import time
import logging
from datetime import date, timedelta
from typing import Optional

import requests

from app.models import db, User

logger = logging.getLogger(__name__)


class OuraAuthError(Exception):
    pass


class OuraClient:
    """Wrapper around Oura API v2."""

    BASE_URL = "https://api.ouraring.com/v2/usercollection"
    TOKEN_URL = "https://cloud.ouraring.com/oauth/token"

    def __init__(self, app_config, user_id: int = 1):
        self._config_client_id = app_config.get("OURA_CLIENT_ID", "")
        self._config_client_secret = app_config.get("OURA_CLIENT_SECRET", "")
        self.user_id = user_id

    @property
    def client_id(self):
        """Database credentials first, .env fallback."""
        user = self._get_user()
        return user.oura_client_id or self._config_client_id

    @property
    def client_secret(self):
        user = self._get_user()
        return user.oura_client_secret or self._config_client_secret

    def _get_user(self) -> User:
        user = db.session.get(User, self.user_id)
        if not user:
            raise OuraAuthError("No user found")
        return user

    def _get_valid_token(self) -> str:
        """Return a valid access token.

        Supports two modes:
        - Personal Access Token (PAT): stored in oura_pat, never expires
        - OAuth access token: stored in oura_access_token, may need refresh
        """
        user = self._get_user()

        # PAT takes priority — simpler, no refresh needed
        if user.oura_pat:
            return user.oura_pat

        if not user.oura_access_token:
            raise OuraAuthError("No Oura token. Go to Settings to connect.")

        # OAuth token — refresh if expiring within 5 minutes
        if user.oura_token_expires_at and user.oura_token_expires_at < time.time() + 300:
            self._refresh_token(user)

        return user.oura_access_token

    def _refresh_token(self, user: User):
        """Use refresh token to get a new access token."""
        if not user.oura_refresh_token:
            raise OuraAuthError("No refresh token. Re-authorize at /auth/oura.")

        resp = requests.post(
            self.TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": user.oura_refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )

        if resp.status_code != 200:
            logger.error(f"Token refresh failed: {resp.status_code}")
            raise OuraAuthError(f"Token refresh failed: {resp.status_code}")

        data = resp.json()
        user.oura_access_token = data["access_token"]
        user.oura_refresh_token = data.get("refresh_token", user.oura_refresh_token)
        user.oura_token_expires_at = time.time() + data.get("expires_in", 86400)
        db.session.commit()

        logger.info("Oura token refreshed successfully")

    def _fetch(self, endpoint: str, start_date: str, end_date: str) -> list:
        """Fetch data from an Oura endpoint for a date range."""
        token = self._get_valid_token()
        url = f"{self.BASE_URL}/{endpoint}"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"start_date": start_date, "end_date": end_date}

        resp = requests.get(url, headers=headers, params=params, timeout=30)

        if resp.status_code == 401:
            raise OuraAuthError("Unauthorized — token may be expired")
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "60")
            logger.warning(f"Rate limited. Retry after {retry_after}s")
            return []
        if resp.status_code != 200:
            logger.error(f"Oura API error on {endpoint}: {resp.status_code}")
            return []

        return resp.json().get("data", [])

    def fetch_daily_activity(self, day: date) -> Optional[dict]:
        """Fetch daily activity for a single day."""
        ds = day.isoformat()
        data = self._fetch("daily_activity", ds, ds)
        if not data:
            return None

        item = data[0]
        return {
            "steps": item.get("steps", 0),
            "calories_burned": item.get("total_calories", 0),
            "active_calories": item.get("active_calories", 0),
            "met_minutes_total": item.get("equivalent_walking_distance"),
            "met_minutes_high": item.get("high_activity_met_minutes"),
            "activity_score": item.get("score"),
        }

    def fetch_daily_sleep(self, day: date) -> Optional[dict]:
        """Fetch daily sleep summary."""
        ds = day.isoformat()
        data = self._fetch("daily_sleep", ds, ds)
        if not data:
            return None

        item = data[0]
        contributors = item.get("contributors", {})
        return {
            "sleep_score": item.get("score"),
            "total_sleep_mins": contributors.get("total_sleep"),
            "deep_sleep_mins": contributors.get("deep_sleep"),
            "rem_sleep_mins": contributors.get("rem_sleep"),
            "sleep_efficiency": contributors.get("efficiency"),
        }

    def fetch_daily_readiness(self, day: date) -> Optional[dict]:
        """Fetch daily readiness."""
        ds = day.isoformat()
        data = self._fetch("daily_readiness", ds, ds)
        if not data:
            return None

        item = data[0]
        contributors = item.get("contributors", {})
        return {
            "readiness_score": item.get("score"),
            "hrv_daily": contributors.get("hrv_balance"),
            "body_temp_deviation": item.get("temperature_deviation"),
            "recovery_index": contributors.get("recovery_index"),
        }

    def fetch_daily_stress(self, day: date) -> Optional[dict]:
        """Fetch daily stress data."""
        ds = day.isoformat()
        data = self._fetch("daily_stress", ds, ds)
        if not data:
            return None

        item = data[0]
        return {
            "stress_high_mins": item.get("stress_high", 0),
            "recovery_high_mins": item.get("recovery_high", 0),
        }

    def fetch_heartrate(self, day: date) -> Optional[dict]:
        """Fetch heart rate summary (derive resting HR from data)."""
        ds = day.isoformat()
        next_day = (day + timedelta(days=1)).isoformat()
        data = self._fetch("heartrate", ds, next_day)
        if not data:
            return None

        bpms = [d.get("bpm", 0) for d in data if d.get("bpm")]
        if not bpms:
            return None

        return {
            "avg_heart_rate": round(sum(bpms) / len(bpms)),
            "resting_heart_rate": min(bpms),
        }

    # Oura activity type mapping to human-friendly names
    ACTIVITY_MAP = {
        "cycling": "Cycling", "walking": "Walking", "running": "Running",
        "hiking": "Hiking", "strength_training": "Strength Training",
        "other": "Other", "yoga": "Yoga", "swimming": "Swimming",
        "dancing": "Dancing", "martial_arts": "Boxing/Martial Arts",
        "indoor_cycling": "Indoor Cycling", "elliptical": "Elliptical",
        "rowing": "Rowing", "pilates": "Pilates",
    }

    def fetch_workouts(self, day: date) -> list:
        """Fetch workouts for a day, parsed into Workout-ready dicts."""
        ds = day.isoformat()
        raw = self._fetch("workout", ds, ds)
        workouts = []

        for item in raw:
            # Parse start time
            start_dt = item.get("start_datetime", "")
            start_time = None
            if start_dt and "T" in start_dt:
                start_time = start_dt.split("T")[1][:5]

            # Duration in minutes
            duration = None
            if item.get("total_seconds"):
                duration = round(item["total_seconds"] / 60)

            # Activity type
            raw_type = item.get("activity", "other").lower()
            activity_type = self.ACTIVITY_MAP.get(raw_type, raw_type.replace("_", " ").title())

            # Intensity from average HR or intensity field
            avg_hr = item.get("average_heart_rate")
            intensity = "medium"
            if avg_hr:
                if avg_hr >= 145:
                    intensity = "high"
                elif avg_hr <= 100:
                    intensity = "low"

            workouts.append({
                "start_time": start_time,
                "duration_mins": duration,
                "activity_type": activity_type,
                "calories": item.get("calories"),
                "avg_heart_rate": avg_hr,
                "intensity": intensity,
                "source": "oura",
            })

        return workouts

    def fetch_all_daily(self, day: date) -> dict:
        """Fetch all daily metrics. Returns a flat dict ready for OuraDaily."""
        result = {}

        for name, fetcher in [
            ("activity", self.fetch_daily_activity),
            ("sleep", self.fetch_daily_sleep),
            ("readiness", self.fetch_daily_readiness),
            ("stress", self.fetch_daily_stress),
            ("heartrate", self.fetch_heartrate),
        ]:
            try:
                data = fetcher(day)
                if data:
                    result.update(data)
            except Exception as e:
                logger.error(f"Error fetching {name} for {day}: {e}")

        return result
