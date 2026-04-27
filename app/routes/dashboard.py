"""Dashboard — the morning view. The heart of the app."""

import logging
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, current_app, redirect, url_for, flash

from app.models import (
    db, User, OuraDaily, GardenState, GardenHistory,
    IFSession, WeightTracking, Notification, Workout, FoodLog,
    CalendarEvent,
)
from app.services.garden_engine import get_level_progress
from app.services.google_calendar import analyze_day

logger = logging.getLogger(__name__)

bp = Blueprint("dashboard", __name__)


def _auto_sync_oura(user, today):
    """Sync today's and yesterday's Oura data if stale or missing.

    Runs quietly on each dashboard load. Keeps it snappy by only syncing
    if we don't already have data for today.
    """
    if not (user.oura_pat or user.oura_access_token):
        return  # Not connected

    # Check if we already have today's data
    has_today = OuraDaily.query.filter_by(user_id=user.id, date=today).first()
    if has_today and has_today.steps is not None:
        return  # Already synced today, skip

    yesterday = today - timedelta(days=1)

    try:
        from app.services.oura_client import OuraClient, OuraAuthError
        client = OuraClient(current_app.config, user_id=user.id)

        # Sync today
        _sync_one_day(client, user.id, today)

        # Also sync yesterday if missing
        has_yesterday = OuraDaily.query.filter_by(user_id=user.id, date=yesterday).first()
        if not has_yesterday:
            _sync_one_day(client, user.id, yesterday)

        # Sync workouts for both days
        _sync_workouts(client, user.id, today)
        _sync_workouts(client, user.id, yesterday)

        # Update garden for yesterday (today's garden can't be scored yet)
        from app.services.garden_engine import update_garden
        update_garden(user.id, yesterday)

        db.session.commit()
        logger.info(f"Auto-sync complete for {today}")

    except Exception as e:
        logger.error(f"Auto-sync failed: {e}")
        db.session.rollback()


def _sync_one_day(client, user_id, day):
    """Fetch and upsert Oura daily data for one day."""
    data = client.fetch_all_daily(day)
    if not data:
        return

    existing = OuraDaily.query.filter_by(user_id=user_id, date=day).first()
    if existing:
        for key, value in data.items():
            if value is not None:
                setattr(existing, key, value)
        existing.synced_at = datetime.utcnow()
    else:
        record = OuraDaily(
            user_id=user_id,
            date=day,
            **{k: v for k, v in data.items() if v is not None},
        )
        db.session.add(record)


def _sync_workouts(client, user_id, day):
    """Fetch and upsert Oura workouts for one day."""
    try:
        workouts = client.fetch_workouts(day)
        for w in workouts:
            existing_w = Workout.query.filter_by(
                user_id=user_id,
                date=day,
                start_time=w.get("start_time"),
                activity_type=w.get("activity_type"),
            ).first()
            if not existing_w:
                workout = Workout(user_id=user_id, date=day, **w)
                db.session.add(workout)
    except Exception as e:
        logger.error(f"Workout sync error for {day}: {e}")


@bp.route("/")
def index():
    """Morning dashboard."""
    user = db.session.get(User, 1)
    today = date.today()
    yesterday = today - timedelta(days=1)

    # Auto-sync Oura data on page load (skips if already fresh)
    _auto_sync_oura(user, today)

    # Yesterday's Oura data
    oura = OuraDaily.query.filter_by(user_id=1, date=yesterday).first()

    # Garden state
    garden = GardenState.query.filter_by(user_id=1).first()
    level_info = get_level_progress(garden.total_seeds) if garden else {
        "level": 1, "total_seeds": 0, "progress_pct": 0, "seeds_to_next": 30
    }

    # Yesterday's seeds
    yesterday_seeds = GardenHistory.query.filter_by(
        user_id=1, date=yesterday
    ).first()

    # IF status
    if_status = _get_if_status(user)

    # IF adherence last 7 days
    week_ago = today - timedelta(days=7)
    if_sessions = IFSession.query.filter(
        IFSession.user_id == 1,
        IFSession.date >= week_ago,
        IFSession.date < today,
    ).all()
    if_adherent = sum(1 for s in if_sessions if s.adherence)
    if_total = len(if_sessions)

    # Latest weight
    latest_weight = WeightTracking.query.filter_by(user_id=1).order_by(
        WeightTracking.date.desc()
    ).first()

    # Previous weight (for trend)
    prev_weight = None
    if latest_weight:
        prev_weight = WeightTracking.query.filter(
            WeightTracking.user_id == 1,
            WeightTracking.date < latest_weight.date,
        ).order_by(WeightTracking.date.desc()).first()

    # Upcoming training
    training = _get_upcoming_training(today)

    # Latest notification/insight
    notification = Notification.query.filter(
        Notification.user_id == 1,
        Notification.dismissed == False,
    ).order_by(Notification.created_at.desc()).first()

    # Days since start (for "Day N" display)
    days_active = GardenHistory.query.filter_by(user_id=1).count()

    # Has Oura been connected? (PAT or OAuth)
    oura_connected = bool(user.oura_pat or user.oura_access_token)

    # Today's Oura data (for movement card — shows today if available, else yesterday)
    oura_today = OuraDaily.query.filter_by(user_id=1, date=today).first()

    # Workouts this week
    week_start = today - timedelta(days=today.weekday())  # Monday
    workouts_this_week = Workout.query.filter(
        Workout.user_id == 1,
        Workout.date >= week_start,
        Workout.date <= today,
    ).order_by(Workout.date.desc()).all()

    # Recent workouts for display (last 3)
    recent_workouts = Workout.query.filter_by(user_id=1).order_by(
        Workout.date.desc()
    ).limit(3).all()

    # Calendar context — only active if connected AND calendars selected
    google_connected = bool(user.google_access_token and user.google_calendar_ids)
    today_events = []
    day_analysis = None
    if google_connected:
        today_events = CalendarEvent.query.filter_by(
            user_id=1, date=today,
        ).order_by(CalendarEvent.start_time).all()
        if today_events:
            day_analysis = analyze_day(1, today)

    # Movement nudge logic (now calendar-aware)
    movement_nudge = _get_movement_nudge(user, today, workouts_this_week, day_analysis)

    # Last sync time
    latest_sync = OuraDaily.query.filter_by(user_id=1).order_by(
        OuraDaily.synced_at.desc()
    ).first()
    last_synced = latest_sync.synced_at if latest_sync else None

    return render_template(
        "dashboard.html",
        user=user,
        today=today,
        yesterday=yesterday,
        oura=oura,
        oura_today=oura_today,
        garden=garden,
        level_info=level_info,
        yesterday_seeds=yesterday_seeds,
        if_status=if_status,
        if_adherent=if_adherent,
        if_total=if_total,
        latest_weight=latest_weight,
        prev_weight=prev_weight,
        training=training,
        notification=notification,
        days_active=days_active,
        oura_connected=oura_connected,
        workouts_this_week=workouts_this_week,
        recent_workouts=recent_workouts,
        movement_nudge=movement_nudge,
        google_connected=google_connected,
        today_events=today_events,
        day_analysis=day_analysis,
        last_synced=last_synced,
    )


@bp.route("/sync", methods=["POST"])
def manual_sync():
    """Manual sync — pull latest data from Oura."""
    user = db.session.get(User, 1)
    today = date.today()
    yesterday = today - timedelta(days=1)

    if not (user.oura_pat or user.oura_access_token):
        flash("Connect Oura first in Settings.", "error")
        return redirect(url_for("dashboard.index"))

    try:
        from app.services.oura_client import OuraClient, OuraAuthError
        from app.services.garden_engine import update_garden

        client = OuraClient(current_app.config, user_id=user.id)

        # Force sync both days
        _sync_one_day(client, user.id, today)
        _sync_one_day(client, user.id, yesterday)
        _sync_workouts(client, user.id, today)
        _sync_workouts(client, user.id, yesterday)
        update_garden(user.id, yesterday)

        db.session.commit()

        # Report what we got
        oura_today = OuraDaily.query.filter_by(user_id=user.id, date=today).first()
        oura_yesterday = OuraDaily.query.filter_by(user_id=user.id, date=yesterday).first()
        steps_today = oura_today.steps if oura_today and oura_today.steps else 0
        steps_yesterday = oura_yesterday.steps if oura_yesterday and oura_yesterday.steps else 0

        flash(f"Synced! Today: {steps_today:,} steps. Yesterday: {steps_yesterday:,} steps.", "success")

    except OuraAuthError as e:
        flash(f"Oura auth error — check your token in Settings.", "error")
        logger.error(f"Manual sync auth error: {e}")
    except Exception as e:
        flash("Sync failed. Check the logs.", "error")
        logger.exception(f"Manual sync error: {e}")

    return redirect(url_for("dashboard.index"))


@bp.route("/api/dashboard")
def api_dashboard():
    """JSON endpoint — same data, for future mobile app."""
    # Phase 2: implement JSON version of the dashboard
    return {"status": "not yet implemented"}, 501


def _get_if_status(user: User) -> dict:
    """Calculate current IF status based on time of day."""
    now = datetime.now()
    current_time = now.strftime("%H:%M")

    start = user.if_start or "11:00"
    end = user.if_end or "19:00"

    start_h, start_m = map(int, start.split(":"))
    end_h, end_m = map(int, end.split(":"))
    now_mins = now.hour * 60 + now.minute
    start_mins = start_h * 60 + start_m
    end_mins = end_h * 60 + end_m

    if now_mins < start_mins:
        remaining = start_mins - now_mins
        hours, mins = divmod(remaining, 60)
        return {
            "status": "fasting",
            "message": f"Eating in {hours}h {mins}m",
            "window": f"{start} – {end}",
        }
    elif now_mins < end_mins:
        remaining = end_mins - now_mins
        hours, mins = divmod(remaining, 60)
        return {
            "status": "eating",
            "message": f"{hours}h {mins}m left",
            "window": f"{start} – {end}",
        }
    else:
        # After eating window — fasting until tomorrow
        remaining = (24 * 60 - now_mins) + start_mins
        hours, mins = divmod(remaining, 60)
        return {
            "status": "fasting",
            "message": f"Next window in {hours}h {mins}m",
            "window": f"{start} – {end}",
        }


def _get_movement_nudge(user: User, today: date, workouts_this_week: list,
                        day_analysis: dict = None) -> dict:
    """Generate a gentle, calendar-aware movement nudge."""
    week_count = len(workouts_this_week)
    target = user.weekly_training_target or 2

    # Check if there was a sweet logged today
    today_sweets = FoodLog.query.filter(
        FoodLog.user_id == user.id,
        FoodLog.date == today,
        FoodLog.category.in_(["sweet", "snack"]),
        FoodLog.chose_not_to == False,
    ).count()

    # Check today's steps
    oura_today = OuraDaily.query.filter_by(user_id=user.id, date=today).first()
    steps_today = oura_today.steps if oura_today and oura_today.steps else 0
    step_target = user.step_target or 8000

    # Calendar-aware nudges take priority when calendar is connected
    if day_analysis:
        if day_analysis["is_busy_day"] and day_analysis["free_gaps"]:
            # Busy day with gaps — suggest using them
            best_gap = max(day_analysis["free_gaps"], key=lambda g: g["duration_mins"])
            return {
                "type": "calendar",
                "message": f"Packed day ahead. You have a {best_gap['duration_mins']}-min gap at {best_gap['start']} \u2014 perfect for a walk.",
            }
        elif day_analysis["is_busy_day"] and not day_analysis["free_gaps"]:
            # Wall-to-wall meetings — empathy, not pressure
            return {
                "type": "calendar",
                "message": "Heavy day \u2014 take it easy. Even a short stretch between calls counts.",
            }
        elif day_analysis["is_light_day"] and week_count < target:
            return {
                "type": "calendar",
                "message": "Light calendar today. Good time for a training session?",
            }
        elif day_analysis["lunch_free"] and steps_today < step_target * 0.3:
            return {
                "type": "calendar",
                "message": "Lunch looks free \u2014 a walk then would grow your meadow.",
            }

    # Non-calendar nudges
    if today_sweets > 0 and steps_today < step_target * 0.5:
        return {
            "type": "gentle",
            "message": "You've enjoyed a treat today. A short walk would keep your garden growing.",
        }
    elif week_count >= target:
        return {
            "type": "praise",
            "message": f"Great week \u2014 {week_count} sessions done! Your stones are growing.",
        }
    elif today.weekday() >= 4 and week_count < target:
        remaining = target - week_count
        return {
            "type": "remind",
            "message": f"Weekend ahead \u2014 {remaining} session{'s' if remaining > 1 else ''} left to hit your weekly target.",
        }
    elif steps_today > 0 and steps_today < step_target * 0.5:
        return {
            "type": "encourage",
            "message": "Still early \u2014 a walk after lunch could get you closer to your step target.",
        }

    return None


def _get_upcoming_training(today: date) -> list:
    """Return next 2 upcoming training sessions."""
    schedule = current_app.config.get("TRAINING_SCHEDULE", [])
    upcoming = []

    for i in range(14):
        check = today + timedelta(days=i)
        for s in schedule:
            if check.weekday() == s["day"]:
                day_name = check.strftime("%A")
                label = "Today" if i == 0 else "Tomorrow" if i == 1 else day_name
                upcoming.append({
                    "date": check,
                    "label": label,
                    "time": s["time"],
                    "type": s["type"],
                })
    return upcoming[:2]
