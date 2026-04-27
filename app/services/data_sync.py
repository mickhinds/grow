"""Daily data sync — runs via cron at 7am.

Fetches yesterday's Oura data, stores it, and updates the garden.
"""

import logging
from datetime import date, timedelta, datetime

from app.models import db, User, OuraDaily, Workout
from app.services.oura_client import OuraClient, OuraAuthError
from app.services.garden_engine import update_garden

logger = logging.getLogger(__name__)


def sync_daily(app, user_id: int = 1, target_date: date = None):
    """Sync yesterday's data from Oura and update garden.

    Args:
        app: Flask app instance (for app context and config)
        user_id: User to sync for
        target_date: Date to sync (defaults to yesterday)
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    with app.app_context():
        logger.info(f"Starting sync for user {user_id}, date {target_date}")

        try:
            client = OuraClient(app.config, user_id=user_id)
            data = client.fetch_all_daily(target_date)
        except OuraAuthError as e:
            logger.error(f"Auth error: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.exception(f"Fetch error: {e}")
            return {"success": False, "error": str(e)}

        if not data:
            logger.warning(f"No data returned for {target_date}")
            return {"success": False, "error": "No data from Oura"}

        # Upsert daily record
        existing = OuraDaily.query.filter_by(
            user_id=user_id, date=target_date
        ).first()

        if existing:
            for key, value in data.items():
                if value is not None:
                    setattr(existing, key, value)
            existing.synced_at = datetime.utcnow()
            logger.info(f"Updated existing record for {target_date}")
        else:
            record = OuraDaily(
                user_id=user_id,
                date=target_date,
                **{k: v for k, v in data.items() if v is not None},
            )
            db.session.add(record)
            logger.info(f"Created new record for {target_date}")

        db.session.commit()

        # Sync workouts
        try:
            workouts = client.fetch_workouts(target_date)
            for w in workouts:
                existing_w = Workout.query.filter_by(
                    user_id=user_id,
                    date=target_date,
                    start_time=w.get("start_time"),
                    activity_type=w.get("activity_type"),
                ).first()
                if not existing_w:
                    workout = Workout(
                        user_id=user_id,
                        date=target_date,
                        **w,
                    )
                    db.session.add(workout)
                    logger.info(f"Added workout: {w['activity_type']} on {target_date}")
            db.session.commit()
        except Exception as e:
            logger.exception(f"Workout sync error: {e}")

        # Update garden
        try:
            history = update_garden(user_id, target_date)
            logger.info(
                f"Garden updated: {history.seeds_total} seeds for {target_date}"
            )
        except Exception as e:
            logger.exception(f"Garden update error: {e}")

        # Sync calendar for today (not target_date — we want today's schedule)
        try:
            user = db.session.get(User, user_id)
            if user and user.google_access_token:
                from app.services.google_calendar import GoogleCalendarClient
                gcal = GoogleCalendarClient(app.config, user_id=user_id)
                today = date.today()
                gcal.sync_events(today)
                logger.info(f"Calendar synced for {today}")
        except Exception as e:
            logger.error(f"Calendar sync error: {e}")

        return {"success": True, "date": target_date.isoformat(), "data": data}


def backfill(app, user_id: int = 1, days: int = 30):
    """Backfill historical data. Useful for initial setup."""
    results = []
    for i in range(days, 0, -1):
        target = date.today() - timedelta(days=i)
        result = sync_daily(app, user_id=user_id, target_date=target)
        results.append(result)
        logger.info(f"Backfill {target}: {result.get('success')}")
    return results
