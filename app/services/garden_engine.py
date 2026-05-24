"""Garden engine — calculates seeds and updates garden state.

The core reward loop. Every good choice earns seeds.
Seeds grow the garden. The garden is you.
"""

import logging
from datetime import date, timedelta
from typing import Optional

from app.models import (
    db, User, OuraDaily, IFSession, FoodLog, Workout,
    GardenState, GardenHistory, MicroHabitCompletion,
)

logger = logging.getLogger(__name__)

# Seed values — tuned for ~8-12 seeds on a good day, ~3-5 on a lazy day
SEEDS_STEP_TARGET = 3          # Hit step target
SEEDS_STEP_BONUS = 1           # 10k+ steps
SEEDS_IF_ADHERENCE = 3         # Maintained eating window
SEEDS_IF_PARTIAL = 1           # Close (within 30 min)
SEEDS_SLEEP_GOOD = 2           # Sleep score 75+
SEEDS_SLEEP_GREAT = 1          # Bonus for 85+
SEEDS_TRAINING = 4             # Kettlebell session
SEEDS_LOGGED_SWEET = 1         # Awareness: logged a sweet
SEEDS_CHOSE_NOT_TO = 2         # Conscious skip
SEEDS_MICRO_HABIT = 1          # Each micro-habit completion
SEEDS_STREAK_7 = 5             # 7-day streak bonus

# Level thresholds (cumulative seeds to reach each level)
LEVEL_THRESHOLDS = [
    0, 30, 80, 160, 280, 450, 680, 1000, 1400, 1900,  # Levels 1-10
    2500, 3200, 4000, 5000, 6200, 7600, 9200, 11000, 13000, 15500,  # 11-20
]


def calculate_seeds_for_day(user: User, day: date) -> dict:
    """Calculate seeds earned for a given day. Returns breakdown dict."""
    seeds = {
        "seeds_steps": 0,
        "seeds_if": 0,
        "seeds_sleep": 0,
        "seeds_training": 0,
        "seeds_awareness": 0,
        "seeds_micro_habits": 0,
        "seeds_bonus": 0,
    }

    # --- Steps ---
    oura = OuraDaily.query.filter_by(user_id=user.id, date=day).first()
    if oura and oura.steps:
        if oura.steps >= user.step_target:
            seeds["seeds_steps"] = SEEDS_STEP_TARGET
            if oura.steps >= 10000:
                seeds["seeds_steps"] += SEEDS_STEP_BONUS

    # --- Sleep ---
    if oura and oura.sleep_score:
        if oura.sleep_score >= 75:
            seeds["seeds_sleep"] = SEEDS_SLEEP_GOOD
            if oura.sleep_score >= 85:
                seeds["seeds_sleep"] += SEEDS_SLEEP_GREAT

    # --- IF adherence ---
    if_session = IFSession.query.filter_by(user_id=user.id, date=day).first()
    if if_session:
        if if_session.adherence:
            seeds["seeds_if"] = SEEDS_IF_ADHERENCE
        else:
            # Partial credit: they logged it, so at least they're aware
            seeds["seeds_if"] = SEEDS_IF_PARTIAL

    # --- Training ---
    # Check actual workouts (synced from Oura or logged manually)
    workouts = Workout.query.filter_by(user_id=user.id, date=day).all()
    if workouts:
        # Base seeds for any workout
        seeds["seeds_training"] = SEEDS_TRAINING
        # Bonus for high-intensity or extra-long sessions
        for w in workouts:
            if w.intensity == "high" or (w.duration_mins and w.duration_mins >= 60):
                seeds["seeds_training"] += 1
                break  # Only one bonus per day

    # Fallback: if no synced workouts yet, check if schedule says training day
    # (covers the case before Oura syncs the workout)
    if not workouts:
        from flask import current_app
        training_schedule = current_app.config.get("TRAINING_SCHEDULE", [])
        is_training_day = any(t["day"] == day.weekday() for t in training_schedule)
        if is_training_day and oura:
            # Only give partial credit — real workout data gets full credit
            seeds["seeds_training"] = SEEDS_TRAINING

    # --- Awareness (food logging) ---
    food_entries = FoodLog.query.filter_by(user_id=user.id, date=day).all()
    for entry in food_entries:
        if entry.chose_not_to:
            seeds["seeds_awareness"] += SEEDS_CHOSE_NOT_TO
        elif entry.category in ("sweet", "snack"):
            seeds["seeds_awareness"] += SEEDS_LOGGED_SWEET

    # --- Micro-habits ---
    micro_completions = MicroHabitCompletion.query.filter_by(
        user_id=user.id, date=day, completed=True
    ).count()
    seeds["seeds_micro_habits"] = micro_completions * SEEDS_MICRO_HABIT

    # --- Streaks ---
    seeds["seeds_bonus"] = _calculate_streak_bonus(user, day)

    return seeds


def _calculate_streak_bonus(user: User, day: date) -> int:
    """Check for 7-day streaks and award bonus seeds."""
    bonus = 0

    # Check IF streak
    streak = 0
    for i in range(7):
        check_date = day - timedelta(days=i)
        session = IFSession.query.filter_by(
            user_id=user.id, date=check_date, adherence=True
        ).first()
        if session:
            streak += 1
        else:
            break
    if streak == 7:
        bonus += SEEDS_STREAK_7

    # Check step streak
    streak = 0
    for i in range(7):
        check_date = day - timedelta(days=i)
        oura = OuraDaily.query.filter_by(user_id=user.id, date=check_date).first()
        if oura and oura.steps and oura.steps >= user.step_target:
            streak += 1
        else:
            break
    if streak == 7:
        bonus += SEEDS_STREAK_7

    return bonus


def update_garden(user_id: int, day: date) -> GardenHistory:
    """Calculate seeds for the day and update garden state."""
    user = db.session.get(User, user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    seeds = calculate_seeds_for_day(user, day)
    total = sum(seeds.values())

    # Upsert garden history
    history = GardenHistory.query.filter_by(user_id=user_id, date=day).first()
    if not history:
        history = GardenHistory(user_id=user_id, date=day)
        db.session.add(history)

    for key, value in seeds.items():
        setattr(history, key, value)
    history.seeds_total = total

    # Update garden state
    garden = GardenState.query.filter_by(user_id=user_id).first()
    if not garden:
        garden = GardenState(user_id=user_id)
        db.session.add(garden)

    garden.total_seeds = _recalculate_total_seeds(user_id)
    garden.level = _calculate_level(garden.total_seeds)

    # Update element growth (0-100 scale, based on recent 30 days)
    _update_element_growth(garden, user_id)

    # Update streaks
    _update_streaks(garden, user)

    db.session.commit()
    return history


def _recalculate_total_seeds(user_id: int) -> int:
    """Sum all seeds ever earned."""
    result = db.session.query(
        db.func.coalesce(db.func.sum(GardenHistory.seeds_total), 0)
    ).filter_by(user_id=user_id).scalar()
    return result


def _calculate_level(total_seeds: int) -> int:
    """Determine level from total seeds."""
    level = 1
    for i, threshold in enumerate(LEVEL_THRESHOLDS):
        if total_seeds >= threshold:
            level = i + 1
        else:
            break
    return level


def _update_element_growth(garden: GardenState, user_id: int):
    """Update garden element growth based on last 30 days of seeds."""
    thirty_days_ago = date.today() - timedelta(days=30)

    recent = GardenHistory.query.filter(
        GardenHistory.user_id == user_id,
        GardenHistory.date >= thirty_days_ago,
    ).all()

    if not recent:
        return

    days = len(recent)
    max_per_element = {
        "meadow": days * (SEEDS_STEP_TARGET + SEEDS_STEP_BONUS),
        "oak": days * SEEDS_IF_ADHERENCE,
        "pond": days * (SEEDS_SLEEP_GOOD + SEEDS_SLEEP_GREAT),
        "stones": (days // 7) * 2 * SEEDS_TRAINING,  # ~2 training days per week
        "path": days * (SEEDS_LOGGED_SWEET + SEEDS_CHOSE_NOT_TO),
    }

    actual = {
        "meadow": sum(h.seeds_steps for h in recent),
        "oak": sum(h.seeds_if for h in recent),
        "pond": sum(h.seeds_sleep for h in recent),
        "stones": sum(h.seeds_training for h in recent),
        "path": sum(h.seeds_awareness for h in recent),
    }

    garden.meadow_growth = min(100, _safe_pct(actual["meadow"], max_per_element["meadow"]))
    garden.oak_growth = min(100, _safe_pct(actual["oak"], max_per_element["oak"]))
    garden.pond_growth = min(100, _safe_pct(actual["pond"], max_per_element["pond"]))
    garden.stones_growth = min(100, _safe_pct(actual["stones"], max_per_element["stones"]))
    garden.path_growth = min(100, _safe_pct(actual["path"], max_per_element["path"]))


def _safe_pct(actual: int, maximum: int) -> int:
    if maximum <= 0:
        return 0
    return round((actual / maximum) * 100)


def _update_streaks(garden: GardenState, user: User):
    """Update current streak counts."""
    today = date.today()

    # IF streak
    streak = 0
    for i in range(365):
        check = today - timedelta(days=i)
        session = IFSession.query.filter_by(
            user_id=user.id, date=check, adherence=True
        ).first()
        if session:
            streak += 1
        else:
            break
    garden.if_streak_days = streak

    # Step streak
    streak = 0
    for i in range(365):
        check = today - timedelta(days=i)
        oura = OuraDaily.query.filter_by(user_id=user.id, date=check).first()
        if oura and oura.steps and oura.steps >= user.step_target:
            streak += 1
        else:
            break
    garden.step_streak_days = streak


def get_level_progress(total_seeds: int) -> dict:
    """Return current level info and progress to next level."""
    level = _calculate_level(total_seeds)
    current_threshold = LEVEL_THRESHOLDS[level - 1] if level <= len(LEVEL_THRESHOLDS) else LEVEL_THRESHOLDS[-1]
    next_threshold = LEVEL_THRESHOLDS[level] if level < len(LEVEL_THRESHOLDS) else current_threshold + 500

    seeds_in_level = total_seeds - current_threshold
    seeds_needed = next_threshold - current_threshold
    progress_pct = round((seeds_in_level / seeds_needed) * 100) if seeds_needed > 0 else 100

    return {
        "level": level,
        "total_seeds": total_seeds,
        "progress_pct": progress_pct,
        "seeds_to_next": next_threshold - total_seeds,
    }
