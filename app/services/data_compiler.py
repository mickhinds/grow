"""Data compiler — gather all user data into structured context for the LLM.

This module replaces the need for a "data agent". Pure Python is better at
reading databases than a 3B language model. The LLM's job is interpretation,
not data retrieval.

The output is a plain dict that gets serialized to JSON and stuffed into
the LLM prompt. Keep it concise — a 3B model has limited context window
(~8K tokens for Ministral 3B). Every token of input costs output quality.

Design principle: compute everything here so the LLM never has to do math.
Don't send raw arrays of daily values — send pre-computed averages, trends,
and deltas. The LLM interprets meaning, Python crunches numbers.
"""

import logging
from datetime import date, timedelta

from app.models import (
    db, User, OuraDaily, IFSession, WeightTracking, Workout,
    FoodLog, GardenState, GardenHistory, CalendarEvent, Disruption,
)
from app.services.google_calendar import analyze_day

logger = logging.getLogger(__name__)


def compile_user_context(user_id: int, today: date = None) -> dict:
    """Build a complete data summary for the LLM.

    Returns a dict with sections:
      - user: name, targets, journey info
      - sleep: last night + 7-day trend
      - movement: steps, workouts, weekly progress
      - fasting: today's status, streak, adherence
      - weight: latest, trend direction
      - calendar: today's density, gaps, pattern
      - garden: level, streaks, recent seeds
      - awareness: recent sweet/skip patterns
      - disruptions: any active life disruptions
      - correlations: pre-computed cross-metric patterns

    All values are pre-computed. The LLM should never need to calculate.
    """
    if today is None:
        today = date.today()

    user = db.session.get(User, user_id)
    if not user:
        return {"error": "User not found"}

    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    two_weeks_ago = today - timedelta(days=14)
    week_start = today - timedelta(days=today.weekday())  # Monday

    context = {
        "date": today.isoformat(),
        "day_of_week": today.strftime("%A"),
        "user": _compile_user(user, today),
        "sleep": _compile_sleep(user_id, yesterday, week_ago),
        "movement": _compile_movement(user_id, user, today, yesterday, week_start, week_ago),
        "fasting": _compile_fasting(user_id, yesterday, week_ago),
        "weight": _compile_weight(user_id),
        "calendar": _compile_calendar(user_id, user, today),
        "garden": _compile_garden(user_id, yesterday),
        "awareness": _compile_awareness(user_id, today, week_ago),
        "disruptions": _compile_disruptions(user_id),
    }

    # Cross-metric correlations (the founding idea of the app)
    context["correlations"] = _compile_correlations(user_id, two_weeks_ago, today)

    return context


def compile_weekly_context(user_id: int, today: date = None) -> dict:
    """Build a weekly summary — used for Sunday reports.

    Higher-level than daily: averages, totals, week-over-week comparisons.
    """
    if today is None:
        today = date.today()

    user = db.session.get(User, user_id)
    week_start = today - timedelta(days=6)  # Last 7 days
    prev_week_start = week_start - timedelta(days=7)

    # This week's Oura data
    this_week = OuraDaily.query.filter(
        OuraDaily.user_id == user_id,
        OuraDaily.date >= week_start,
        OuraDaily.date <= today,
    ).all()

    prev_week = OuraDaily.query.filter(
        OuraDaily.user_id == user_id,
        OuraDaily.date >= prev_week_start,
        OuraDaily.date < week_start,
    ).all()

    def avg(items, attr):
        vals = [getattr(i, attr) for i in items if getattr(i, attr) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    # Workouts this week
    workouts = Workout.query.filter(
        Workout.user_id == user_id,
        Workout.date >= week_start,
        Workout.date <= today,
    ).all()

    total_mins = sum(w.duration_mins or 0 for w in workouts)
    workout_types = list(set(w.activity_type for w in workouts if w.activity_type))

    # IF adherence
    if_sessions = IFSession.query.filter(
        IFSession.user_id == user_id,
        IFSession.date >= week_start,
        IFSession.date <= today,
    ).all()
    if_adherent = sum(1 for s in if_sessions if s.adherence)

    # Sweets vs skips
    food = FoodLog.query.filter(
        FoodLog.user_id == user_id,
        FoodLog.date >= week_start,
        FoodLog.date <= today,
    ).all()
    sweets = sum(1 for f in food if not f.chose_not_to and f.category in ("sweet", "snack"))
    skips = sum(1 for f in food if f.chose_not_to)

    # Weight change
    weights = WeightTracking.query.filter(
        WeightTracking.user_id == user_id,
        WeightTracking.date >= week_start,
    ).order_by(WeightTracking.date).all()

    return {
        "period": f"{week_start.isoformat()} to {today.isoformat()}",
        "user_name": user.name,
        "sleep": {
            "avg_score": avg(this_week, "sleep_score"),
            "prev_avg_score": avg(prev_week, "sleep_score"),
            "avg_duration_hrs": round(avg(this_week, "total_sleep_mins") / 60, 1) if avg(this_week, "total_sleep_mins") else None,
            "best_night": max((d.sleep_score for d in this_week if d.sleep_score), default=None),
            "worst_night": min((d.sleep_score for d in this_week if d.sleep_score), default=None),
        },
        "movement": {
            "avg_steps": avg(this_week, "steps"),
            "prev_avg_steps": avg(prev_week, "steps"),
            "total_workout_mins": total_mins,
            "target_mins": user.weekly_activity_target_mins or 150,
            "workout_types": workout_types,
            "workout_count": len(workouts),
        },
        "fasting": {
            "days_tracked": len(if_sessions),
            "days_adherent": if_adherent,
        },
        "awareness": {
            "sweets": sweets,
            "conscious_skips": skips,
        },
        "weight": {
            "entries": [{"date": w.date.isoformat(), "kg": w.weight_kg} for w in weights],
        },
        "readiness": {
            "avg_score": avg(this_week, "readiness_score"),
            "prev_avg_score": avg(prev_week, "readiness_score"),
        },
        "hrv": {
            "avg": avg(this_week, "hrv_daily"),
            "prev_avg": avg(prev_week, "hrv_daily"),
        },
    }


# --- Section compilers ---

def _compile_user(user: User, today: date) -> dict:
    days_active = (today - user.start_date).days + 1 if user.start_date else 0
    return {
        "name": user.name,
        "days_active": days_active,
        "step_target": user.step_target,
        "activity_target_mins": user.weekly_activity_target_mins or 150,
        "target_weight_kg": user.target_weight_kg,
        "weekly_focus": user.weekly_focus,
    }


def _compile_sleep(user_id: int, yesterday: date, week_ago: date) -> dict:
    last_night = OuraDaily.query.filter_by(user_id=user_id, date=yesterday).first()
    week = OuraDaily.query.filter(
        OuraDaily.user_id == user_id,
        OuraDaily.date >= week_ago,
        OuraDaily.date <= yesterday,
        OuraDaily.sleep_score.isnot(None),
    ).all()

    avg_score = round(sum(d.sleep_score for d in week) / len(week), 1) if week else None

    result = {"last_night": None, "week_avg_score": avg_score}
    if last_night and last_night.sleep_score:
        result["last_night"] = {
            "score": last_night.sleep_score,
            "duration_hrs": round(last_night.total_sleep_mins / 60, 1) if last_night.total_sleep_mins else None,
            "deep_mins": last_night.deep_sleep_mins,
            "resting_hr": last_night.resting_heart_rate,
            "hrv": round(last_night.hrv_daily, 1) if last_night.hrv_daily else None,
            "readiness": last_night.readiness_score,
            "vs_avg": round(last_night.sleep_score - avg_score, 1) if avg_score else None,
        }
    return result


def _compile_movement(user_id, user, today, yesterday, week_start, week_ago):
    oura_yesterday = OuraDaily.query.filter_by(user_id=user_id, date=yesterday).first()
    oura_today = OuraDaily.query.filter_by(user_id=user_id, date=today).first()

    # Weekly workout minutes
    workouts = Workout.query.filter(
        Workout.user_id == user_id,
        Workout.date >= week_start,
        Workout.date <= today,
    ).all()
    week_mins = sum(w.duration_mins or 0 for w in workouts)
    target = user.weekly_activity_target_mins or 150

    # Step average over week
    week_steps = OuraDaily.query.filter(
        OuraDaily.user_id == user_id,
        OuraDaily.date >= week_ago,
        OuraDaily.steps.isnot(None),
    ).all()
    avg_steps = round(sum(d.steps for d in week_steps) / len(week_steps)) if week_steps else None

    return {
        "steps_yesterday": oura_yesterday.steps if oura_yesterday else None,
        "steps_today": oura_today.steps if oura_today else None,
        "step_target": user.step_target,
        "steps_week_avg": avg_steps,
        "workout_mins_this_week": week_mins,
        "workout_target_mins": target,
        "workout_pct": round(week_mins / target * 100) if target > 0 else 0,
        "active_days": len(set(w.date for w in workouts)),
    }


def _compile_fasting(user_id, yesterday, week_ago):
    today_if = IFSession.query.filter_by(user_id=user_id, date=yesterday).first()

    # Streak
    streak = 0
    for i in range(30):
        check = yesterday - timedelta(days=i)
        s = IFSession.query.filter_by(user_id=user_id, date=check, adherence=True).first()
        if s:
            streak += 1
        else:
            break

    # Week adherence
    week = IFSession.query.filter(
        IFSession.user_id == user_id,
        IFSession.date >= week_ago,
    ).all()

    return {
        "yesterday_adherence": today_if.adherence if today_if else None,
        "streak_days": streak,
        "week_logged": len(week),
        "week_adherent": sum(1 for s in week if s.adherence),
    }


def _compile_weight(user_id):
    latest = WeightTracking.query.filter_by(user_id=user_id).order_by(
        WeightTracking.date.desc()
    ).first()

    if not latest:
        return {"latest": None}

    # Get oldest for long-term trend
    oldest = WeightTracking.query.filter_by(user_id=user_id).order_by(
        WeightTracking.date
    ).first()

    result = {
        "latest": {
            "kg": latest.weight_kg,
            "date": latest.date.isoformat(),
            "waist_cm": latest.waist_cm,
        },
    }

    if oldest and oldest.id != latest.id:
        days = (latest.date - oldest.date).days
        delta = latest.weight_kg - oldest.weight_kg
        result["trend"] = {
            "total_change_kg": round(delta, 1),
            "over_days": days,
            "direction": "down" if delta < 0 else "up" if delta > 0 else "stable",
        }

    return result


def _compile_calendar(user_id, user, today):
    if not (user.google_access_token and user.google_calendar_ids):
        return {"connected": False}

    try:
        analysis = analyze_day(user_id, today)
    except Exception:
        return {"connected": True, "error": "sync failed"}

    if not analysis:
        return {"connected": True, "no_events": True}

    return {
        "connected": True,
        "total_meetings": analysis.get("total_meetings", 0),
        "is_busy_day": analysis.get("is_busy_day", False),
        "is_light_day": analysis.get("is_light_day", False),
        "free_gaps": [
            {"start": g["start"], "duration_mins": g["duration_mins"]}
            for g in analysis.get("free_gaps", [])
        ],
        "lunch_free": analysis.get("lunch_free", True),
    }


def _compile_garden(user_id, yesterday):
    garden = GardenState.query.filter_by(user_id=user_id).first()
    yesterday_hist = GardenHistory.query.filter_by(user_id=user_id, date=yesterday).first()

    if not garden:
        return {"level": 1, "total_seeds": 0}

    from app.services.garden_engine import get_level_progress
    level_info = get_level_progress(garden.total_seeds)

    return {
        "level": level_info["level"],
        "total_seeds": garden.total_seeds,
        "progress_pct": level_info["progress_pct"],
        "seeds_to_next": level_info["seeds_to_next"],
        "yesterday_seeds": yesterday_hist.seeds_total if yesterday_hist else 0,
        "streaks": {
            "if": garden.if_streak_days,
            "steps": garden.step_streak_days,
            "sleep": garden.sleep_streak_days,
        },
    }


def _compile_awareness(user_id, today, week_ago):
    week_food = FoodLog.query.filter(
        FoodLog.user_id == user_id,
        FoodLog.date >= week_ago,
        FoodLog.date <= today,
    ).all()

    return {
        "sweets_this_week": sum(1 for f in week_food if not f.chose_not_to and f.category in ("sweet", "snack")),
        "skips_this_week": sum(1 for f in week_food if f.chose_not_to),
    }


def _compile_disruptions(user_id):
    active = Disruption.query.filter(
        Disruption.user_id == user_id,
        Disruption.status.in_(["active", "adapting", "recovering"]),
    ).all()

    return [
        {
            "type": d.disruption_type,
            "title": d.title,
            "severity": d.severity,
            "days_in": (date.today() - d.start_date).days,
            "affects": {
                "movement": d.affects_movement,
                "training": d.affects_training,
                "sleep": d.affects_sleep,
            },
        }
        for d in active
    ]


def _compile_correlations(user_id, start_date, end_date):
    """Pre-compute cross-metric correlations.

    This is the founding idea: how does calendar density affect sleep,
    steps, and readiness? Python does the math, LLM finds the narrative.
    """
    days = OuraDaily.query.filter(
        OuraDaily.user_id == user_id,
        OuraDaily.date >= start_date,
        OuraDaily.date <= end_date,
    ).all()

    if len(days) < 7:
        return {"insufficient_data": True}

    # Calendar density per day (meeting count)
    events_by_date = {}
    events = CalendarEvent.query.filter(
        CalendarEvent.user_id == user_id,
        CalendarEvent.date >= start_date,
        CalendarEvent.date <= end_date,
        CalendarEvent.is_all_day == False,
    ).all()

    for e in events:
        events_by_date.setdefault(e.date, 0)
        events_by_date[e.date] += 1

    # Split days into busy (5+ meetings) and light (0-2 meetings)
    busy_days_oura = [d for d in days if events_by_date.get(d.date, 0) >= 5]
    light_days_oura = [d for d in days if events_by_date.get(d.date, 0) <= 2]

    def safe_avg(items, attr):
        vals = [getattr(i, attr) for i in items if getattr(i, attr) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    result = {}

    if len(busy_days_oura) >= 3 and len(light_days_oura) >= 3:
        busy_sleep = safe_avg(busy_days_oura, "sleep_score")
        light_sleep = safe_avg(light_days_oura, "sleep_score")
        busy_steps = safe_avg(busy_days_oura, "steps")
        light_steps = safe_avg(light_days_oura, "steps")

        if busy_sleep and light_sleep:
            result["sleep_vs_meetings"] = {
                "busy_avg": busy_sleep,
                "light_avg": light_sleep,
                "delta": round(light_sleep - busy_sleep, 1),
                "note": (
                    f"Sleep scores average {round(light_sleep - busy_sleep, 1)} points higher "
                    f"on light days vs busy days"
                ) if light_sleep > busy_sleep else None,
            }

        if busy_steps and light_steps:
            result["steps_vs_meetings"] = {
                "busy_avg": round(busy_steps),
                "light_avg": round(light_steps),
                "delta": round(light_steps - busy_steps),
            }

    return result if result else {"insufficient_data": True}
