"""Dashboard — the morning view. The heart of the app."""

import logging
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, current_app, redirect, url_for, flash, request

from app.models import (
    db, User, OuraDaily, GardenState, GardenHistory,
    IFSession, WeightTracking, Notification, Workout, FoodLog,
    CalendarEvent, Disruption,
)
from app.services.garden_engine import get_level_progress
from app.services.google_calendar import analyze_day
from app.services.micro_habits import get_todays_micro_habits
from app.services.status_sentence import compose_status_sentence, get_focus_suggestions
from app.services.anomaly import detect_anomalies

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


def _auto_sync_calendar(user, today):
    """Auto-sync today's Google Calendar events if stale or missing.

    Syncs on every dashboard load if we haven't synced in the last 30 minutes.
    Calendar data changes frequently (new meetings, cancellations), so
    we sync more aggressively than Oura.
    """
    if not (user.google_access_token and user.google_calendar_ids):
        return

    # Check if we have recent events — use synced_at to determine freshness
    latest_event = CalendarEvent.query.filter_by(
        user_id=user.id, date=today,
    ).order_by(CalendarEvent.synced_at.desc()).first()

    # Sync if no events exist OR if last sync was > 30 min ago
    if latest_event and latest_event.synced_at:
        age_mins = (datetime.utcnow() - latest_event.synced_at).total_seconds() / 60
        if age_mins < 30:
            return  # Fresh enough

    try:
        from app.services.google_calendar import GoogleCalendarClient
        client = GoogleCalendarClient(current_app.config, user_id=user.id)
        client.sync_events(today)
        logger.info(f"Calendar auto-sync complete for {today}")
    except Exception as e:
        logger.error(f"Calendar auto-sync failed: {e}")


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

    # Days since start — counted from user.start_date (set on reset/first use)
    if user.start_date:
        days_active = (today - user.start_date).days + 1  # Day 1 on start date
    else:
        days_active = 0

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

    # Calendar context — auto-sync + analyze
    google_connected = bool(user.google_access_token and user.google_calendar_ids)
    today_events = []
    day_analysis = None
    if google_connected:
        _auto_sync_calendar(user, today)
        today_events = CalendarEvent.query.filter_by(
            user_id=1, date=today,
        ).order_by(CalendarEvent.start_time).all()
        day_analysis = analyze_day(1, today)

    # Micro-habits for today
    micro_habits = get_todays_micro_habits(user.id, today)

    # Greeting — time-based + contextual
    greeting = _get_greeting(user, oura, day_analysis)

    # Status sentence — the voice of the app
    status_sentence = compose_status_sentence(user, today)

    # Weekly focus
    focus_suggestions = []
    needs_focus = False
    if not user.weekly_focus or (user.weekly_focus_set_date and
            (today - user.weekly_focus_set_date).days >= 7):
        needs_focus = True
        focus_suggestions = get_focus_suggestions(user, today)

    # Anomaly cards — only show when something is notably different
    anomalies = detect_anomalies(user.id, today)

    # Active disruptions
    active_disruptions = Disruption.query.filter_by(
        user_id=1, status="active"
    ).order_by(Disruption.created_at.desc()).all()
    adapting_disruptions = Disruption.query.filter_by(
        user_id=1, status="adapting"
    ).order_by(Disruption.created_at.desc()).all()

    # Movement nudge logic (now calendar-aware)
    movement_nudge = _get_movement_nudge(user, today, workouts_this_week, day_analysis)

    # Last sync time
    latest_sync = OuraDaily.query.filter_by(user_id=1).order_by(
        OuraDaily.synced_at.desc()
    ).first()
    last_synced = latest_sync.synced_at if latest_sync else None

    # Weekly activity minutes (computed here, not in template, to handle None)
    week_activity_mins = sum(w.duration_mins or 0 for w in workouts_this_week)
    activity_target = user.weekly_activity_target_mins or 150

    return render_template(
        "dashboard.html",
        user=user,
        today=today,
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
        days_active=days_active,
        oura_connected=oura_connected,
        workouts_this_week=workouts_this_week,
        recent_workouts=recent_workouts,
        week_activity_mins=week_activity_mins,
        activity_target=activity_target,
        movement_nudge=movement_nudge,
        micro_habits=micro_habits,
        google_connected=google_connected,
        today_events=today_events,
        last_synced=last_synced,
        greeting=greeting,
        status_sentence=status_sentence,
        needs_focus=needs_focus,
        focus_suggestions=focus_suggestions,
        anomalies=anomalies,
        active_disruptions=active_disruptions,
        adapting_disruptions=adapting_disruptions,
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


@bp.route("/focus", methods=["POST"])
def set_focus():
    """Set the weekly focus — what matters most this week."""
    user = db.session.get(User, 1)
    focus_key = request.form.get("focus", "").strip()
    valid_keys = ["steps", "if", "sleep", "training", "awareness", "nutrition"]
    if focus_key not in valid_keys:
        flash("Pick a focus area.", "error")
        return redirect(url_for("dashboard.index"))

    labels = {
        "steps": "Steps consistency",
        "if": "Fasting window",
        "sleep": "Sleep quality",
        "training": "Training consistency",
        "awareness": "Daily logging",
        "nutrition": "Balanced meals",
    }

    user.weekly_focus = focus_key
    user.weekly_focus_label = labels.get(focus_key, focus_key)
    user.weekly_focus_set_date = date.today()
    db.session.commit()

    flash(f"This week: {labels.get(focus_key)}.", "success")
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
    week_mins = sum(w.duration_mins or 0 for w in workouts_this_week)
    target_mins = user.weekly_activity_target_mins or 150

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

    # Calendar nudges disabled until calendar sync is reliable
    # (user feedback: "looks like a light day" when day is fully packed)
    if False and day_analysis:
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
        elif day_analysis["is_light_day"] and week_mins < target_mins:
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
    elif week_mins >= target_mins:
        return {
            "type": "praise",
            "message": f"Strong week \u2014 {week_mins} min logged! Your stones are growing.",
        }
    elif today.weekday() >= 4 and week_mins < target_mins:
        remaining = target_mins - week_mins
        return {
            "type": "remind",
            "message": f"Weekend ahead \u2014 {remaining} min left to hit your weekly target.",
        }
    elif steps_today > 0 and steps_today < step_target * 0.5:
        return {
            "type": "encourage",
            "message": "Still early \u2014 a walk after lunch could get you closer to your step target.",
        }

    return None


def _get_greeting(user: User, oura_yesterday, day_analysis, visit_count: int = 1) -> str:
    """Build a time-based + contextual greeting.

    Not coaching, not cheerleading. Curious.
    """
    now = datetime.now()
    hour = now.hour
    name = user.name or ""

    # Time-based base
    if hour < 5:
        base = f"Can't sleep, {name}?"
    elif hour < 7:
        base = f"Early start, {name}"
    elif hour < 10:
        base = f"Good morning, {name}"
    elif hour < 12:
        base = f"Morning, {name}"
    elif hour < 17:
        base = f"Afternoon, {name}"
    elif hour < 21:
        base = f"Evening, {name}"
    else:
        base = f"Still up, {name}?"

    # Contextual overrides — only one, the most relevant
    if visit_count > 1:
        # Not the first dashboard load today
        if hour < 12:
            return f"Back again, {name}"
        elif hour >= 21:
            return f"One more look, {name}?"
        else:
            return f"Checking in, {name}"

    if oura_yesterday:
        # Rough night
        if oura_yesterday.sleep_score and oura_yesterday.sleep_score < 55 and hour < 10:
            return f"Rough night? Take it easy, {name}"
        # Great readiness
        if oura_yesterday.readiness_score and oura_yesterday.readiness_score >= 85 and hour < 12:
            return f"Looking sharp today, {name}"

    if day_analysis:
        if day_analysis.get("is_busy_day") and hour < 12:
            return f"Full day ahead, {name}"
        elif day_analysis.get("is_light_day") and hour < 12:
            return f"Open day today, {name}"

    return base


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
