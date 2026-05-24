"""Status sentence — one line that captures yesterday, today, and what matters.

The voice of the app. Curious, not coaching. Short, not chatty.
Rule-based for now. Slot for AI-composed when Ministral 3B runs.
"""

from datetime import date, timedelta
from app.models import (
    db, User, OuraDaily, IFSession, Workout, GardenHistory,
    Disruption, GardenState,
)


def compose_status_sentence(user: User, today: date) -> str:
    """Build a single contextual sentence from yesterday's data and today's context."""
    yesterday = today - timedelta(days=1)

    # Gather data
    oura = OuraDaily.query.filter_by(user_id=user.id, date=yesterday).first()
    if_session = IFSession.query.filter_by(user_id=user.id, date=yesterday).first()
    workouts = Workout.query.filter_by(user_id=user.id, date=yesterday).all()
    garden_hist = GardenHistory.query.filter_by(user_id=user.id, date=yesterday).first()
    active_disruption = Disruption.query.filter(
        Disruption.user_id == user.id,
        Disruption.status.in_(["active", "adapting"]),
    ).first()

    # Check inactivity — no data at all recently
    days_since_activity = _days_since_last_activity(user.id, today)

    # Calendar context (if connected)
    day_analysis = None
    if user.google_access_token and user.google_calendar_ids:
        try:
            from app.services.google_calendar import analyze_day
            day_analysis = analyze_day(user.id, today)
        except Exception:
            pass

    # --- Priority-ordered sentence generation ---

    # 1. Inactivity (2+ days)
    if days_since_activity >= 3:
        return "It's been a few days. Everything okay, or is something going on?"
    if days_since_activity == 2:
        return "Been a quiet couple of days. Pick one thing and let's go."

    # 2. Active disruption
    if active_disruption:
        days_in = (today - active_disruption.start_date).days
        if active_disruption.disruption_type == "injury":
            can = active_disruption.can_still_do or "gentle movement"
            return f"Day {days_in} of recovery. {can.capitalize()} — that's plenty."
        elif active_disruption.disruption_type == "work_stress":
            return f"Stress week, day {days_in}. Small actions count — just the micro-habits today."
        elif active_disruption.disruption_type == "illness":
            return "Still recovering. Rest is the priority. One micro-habit if you're up for it."
        else:
            return f"{active_disruption.title} — day {days_in}. What feels manageable today?"

    # 3. Yesterday highlights + today context
    parts = []

    # Steps
    if oura and oura.steps:
        if oura.steps >= user.step_target:
            parts.append(f"{oura.steps:,} steps yesterday")
        elif oura.steps >= user.step_target * 0.8:
            parts.append(f"Close on steps — {oura.steps:,}")

    # IF
    if if_session and if_session.adherence:
        # Count current IF streak
        streak = _count_if_streak(user.id, yesterday)
        if streak >= 5:
            parts.append(f"IF on track, {streak} days running")
        else:
            parts.append("IF on track")

    # Training
    if workouts:
        types = [w.activity_type for w in workouts if w.activity_type]
        if types:
            parts.append(f"{types[0].lower()} session done")

    # Seeds
    if garden_hist and garden_hist.seeds_total > 0:
        parts.append(f"+{garden_hist.seeds_total} seeds")

    # Compose yesterday part
    if parts:
        yesterday_part = ", ".join(parts[:2]) + "."
    else:
        yesterday_part = ""

    # Today part — calendar or focus based
    today_part = ""
    if day_analysis:
        if day_analysis.get("is_busy_day"):
            today_part = " Full day ahead — small wins count."
        elif day_analysis.get("is_light_day"):
            # Suggest based on focus or training
            week_start = today - timedelta(days=today.weekday())
            week_workouts = Workout.query.filter(
                Workout.user_id == user.id,
                Workout.date >= week_start,
                Workout.date <= today,
            ).count()
            target = user.weekly_training_target or 2
            if week_workouts < target:
                today_part = " Light calendar — good for a training session?"
            else:
                today_part = " Open day. Nice pace this week."
    elif user.weekly_focus:
        today_part = f" Focus this week: {_focus_to_text(user.weekly_focus)}."

    # Sleep-based opener override
    if oura and oura.sleep_score and oura.sleep_score < 55:
        return f"Rough sleep last night.{today_part or ' Take it easy today.'}"

    if yesterday_part:
        return yesterday_part + today_part
    else:
        # No data from yesterday
        return "New day. What matters today?"


def get_focus_suggestions(user: User, today: date) -> list:
    """Generate 3-4 data-informed focus suggestions for the week."""
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    suggestions = []

    # Check step consistency
    step_days = OuraDaily.query.filter(
        OuraDaily.user_id == user.id,
        OuraDaily.date >= week_ago,
        OuraDaily.steps >= user.step_target,
    ).count()
    total_days = OuraDaily.query.filter(
        OuraDaily.user_id == user.id,
        OuraDaily.date >= week_ago,
        OuraDaily.steps.isnot(None),
    ).count()
    if total_days > 0 and step_days < total_days * 0.6:
        suggestions.append({
            "key": "steps",
            "label": "Steps consistency",
            "detail": f"Hit target {step_days} of {total_days} days last week",
        })

    # Check IF adherence
    if_sessions = IFSession.query.filter(
        IFSession.user_id == user.id,
        IFSession.date >= week_ago,
    ).all()
    if_adherent = sum(1 for s in if_sessions if s.adherence)
    if len(if_sessions) < 5 or (len(if_sessions) > 0 and if_adherent < len(if_sessions) * 0.7):
        suggestions.append({
            "key": "if",
            "label": "Fasting window",
            "detail": f"{if_adherent}/{len(if_sessions)} days on track last week",
        })

    # Check sleep
    sleep_days = OuraDaily.query.filter(
        OuraDaily.user_id == user.id,
        OuraDaily.date >= week_ago,
        OuraDaily.sleep_score.isnot(None),
    ).all()
    avg_sleep = sum(d.sleep_score for d in sleep_days) / len(sleep_days) if sleep_days else 0
    if avg_sleep > 0 and avg_sleep < 72:
        suggestions.append({
            "key": "sleep",
            "label": "Sleep quality",
            "detail": f"Average score {avg_sleep:.0f} last week",
        })

    # Check training
    week_start = today - timedelta(days=today.weekday())
    prev_week_start = week_start - timedelta(days=7)
    prev_workouts = Workout.query.filter(
        Workout.user_id == user.id,
        Workout.date >= prev_week_start,
        Workout.date < week_start,
    ).count()
    target = user.weekly_training_target or 2
    if prev_workouts < target:
        suggestions.append({
            "key": "training",
            "label": "Training consistency",
            "detail": f"{prev_workouts}/{target} sessions last week",
        })

    # Always offer awareness as an option
    if len(suggestions) < 4:
        suggestions.append({
            "key": "awareness",
            "label": "Daily logging",
            "detail": "Log something every day this week",
        })

    return suggestions[:4]


def _days_since_last_activity(user_id: int, today: date) -> int:
    """Count consecutive days without any logged activity."""
    for i in range(1, 30):
        check = today - timedelta(days=i)
        # Check if anything was logged that day
        has_oura = OuraDaily.query.filter_by(user_id=user_id, date=check).first()
        has_if = IFSession.query.filter_by(user_id=user_id, date=check).first()
        has_garden = GardenHistory.query.filter_by(user_id=user_id, date=check).first()
        if has_oura or has_if or has_garden:
            return i - 1
    return 30


def _count_if_streak(user_id: int, from_date: date) -> int:
    """Count consecutive IF adherence days backwards from a date."""
    streak = 0
    for i in range(30):
        check = from_date - timedelta(days=i)
        session = IFSession.query.filter_by(
            user_id=user_id, date=check, adherence=True
        ).first()
        if session:
            streak += 1
        else:
            break
    return streak


def _focus_to_text(focus_key: str) -> str:
    """Convert focus key to readable text."""
    mapping = {
        "steps": "steps consistency",
        "if": "fasting window",
        "sleep": "sleep quality",
        "training": "training consistency",
        "awareness": "daily logging",
        "nutrition": "balanced meals",
    }
    return mapping.get(focus_key, focus_key)
