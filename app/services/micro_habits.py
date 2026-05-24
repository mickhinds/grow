"""Micro-habit engine — the smallest meaningful actions.

Selects 1-3 micro-habits per day based on context:
- Yesterday's Oura data (sleep, steps)
- Today's calendar (busy vs. light)
- Recent activity patterns
- What hasn't been suggested recently

Each completed micro-habit earns 1 seed. The point isn't the action —
it's the identity reinforcement. Showing up matters more than performance.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from app.models import (
    db, User, OuraDaily, MicroHabit, MicroHabitCompletion,
    Workout, CalendarEvent,
)

logger = logging.getLogger(__name__)

SEEDS_PER_MICRO_HABIT = 1
MAX_DAILY_SUGGESTIONS = 3


def get_todays_micro_habits(user_id: int, today: date = None) -> list:
    """Get today's suggested micro-habits. Creates suggestions if none exist yet.

    Returns list of dicts: {id, completion_id, text, category, completed, dismissed}
    """
    if today is None:
        today = date.today()

    # Check if we already have suggestions for today
    existing = MicroHabitCompletion.query.filter_by(
        user_id=user_id, date=today, suggested=True
    ).all()

    if existing:
        return _format_suggestions(existing)

    # No suggestions yet — generate them
    suggestions = _select_micro_habits(user_id, today)

    for habit in suggestions:
        completion = MicroHabitCompletion(
            user_id=user_id,
            date=today,
            micro_habit_id=habit.id,
            suggested=True,
        )
        db.session.add(completion)

    db.session.commit()

    # Re-fetch to get IDs
    created = MicroHabitCompletion.query.filter_by(
        user_id=user_id, date=today, suggested=True
    ).all()

    return _format_suggestions(created)


def complete_micro_habit(completion_id: int) -> bool:
    """Mark a micro-habit as completed. Returns True if successful."""
    completion = db.session.get(MicroHabitCompletion, completion_id)
    if not completion or completion.completed:
        return False

    completion.completed = True
    completion.completed_at = datetime.utcnow()
    completion.dismissed = False
    db.session.commit()

    # Update garden
    from app.services.garden_engine import update_garden
    update_garden(completion.user_id, completion.date)

    return True


def dismiss_micro_habit(completion_id: int) -> bool:
    """Dismiss a micro-habit suggestion. Returns True if successful."""
    completion = db.session.get(MicroHabitCompletion, completion_id)
    if not completion:
        return False

    completion.dismissed = True
    db.session.commit()
    return True


def count_completed_today(user_id: int, day: date = None) -> int:
    """Count completed micro-habits for a given day."""
    if day is None:
        day = date.today()

    return MicroHabitCompletion.query.filter_by(
        user_id=user_id, date=day, completed=True
    ).count()


def _select_micro_habits(user_id: int, today: date) -> list:
    """Rule-based selection of 1-3 micro-habits for today.

    Considers:
    - Yesterday's sleep quality
    - Yesterday's/today's step count
    - Whether it's a training day
    - Calendar density (if available)
    - What was suggested recently (avoid repeats)
    """
    user = db.session.get(User, user_id)
    yesterday = today - timedelta(days=1)

    # Gather context
    oura_yesterday = OuraDaily.query.filter_by(user_id=user_id, date=yesterday).first()
    oura_today = OuraDaily.query.filter_by(user_id=user_id, date=today).first()

    # Today's workouts (to know if it's a training day)
    todays_workouts = Workout.query.filter_by(user_id=user_id, date=today).count()

    # Calendar context
    today_events = CalendarEvent.query.filter_by(user_id=user_id, date=today).count()
    is_busy = today_events >= 5
    is_light = today_events <= 2

    # Recent suggestions (last 3 days) — avoid repeats
    three_days_ago = today - timedelta(days=3)
    recent_habit_ids = [
        c.micro_habit_id for c in
        MicroHabitCompletion.query.filter(
            MicroHabitCompletion.user_id == user_id,
            MicroHabitCompletion.date >= three_days_ago,
            MicroHabitCompletion.date < today,
        ).all()
    ]

    # Determine context flags
    low_steps = False
    poor_sleep = False
    no_training = todays_workouts == 0

    if oura_yesterday:
        if oura_yesterday.steps and user.step_target:
            low_steps = oura_yesterday.steps < (user.step_target * 0.6)
        if oura_yesterday.sleep_score:
            poor_sleep = oura_yesterday.sleep_score < 70

    # If we have today's data, use that for steps
    if oura_today and oura_today.steps and user.step_target:
        low_steps = oura_today.steps < (user.step_target * 0.5)

    # Get all active habits
    all_habits = MicroHabit.query.filter_by(active=True).all()
    if not all_habits:
        return []

    # Score each habit based on context match
    scored = []
    for habit in all_habits:
        # Skip if suggested in last 3 days
        if habit.id in recent_habit_ids:
            continue

        score = 1  # Base score

        # Boost score for context matches
        if habit.requires_low_steps and low_steps:
            score += 3
        if habit.requires_poor_sleep and poor_sleep:
            score += 3
        if habit.requires_no_training and no_training:
            score += 2
        if habit.requires_busy_day and is_busy:
            score += 2
        if habit.requires_light_day and is_light:
            score += 2

        # Slight penalty if context flags are set but don't match
        if habit.requires_low_steps and not low_steps:
            score -= 1
        if habit.requires_poor_sleep and not poor_sleep:
            score -= 1
        if habit.requires_busy_day and not is_busy:
            score -= 1
        if habit.requires_light_day and not is_light:
            score -= 1

        scored.append((score, habit))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Pick top habits, ensuring category diversity
    selected = []
    used_categories = set()

    for score, habit in scored:
        if len(selected) >= MAX_DAILY_SUGGESTIONS:
            break

        # Prefer different categories (allow same category only if we need to)
        if habit.category in used_categories and len(selected) < 2:
            continue

        selected.append(habit)
        used_categories.add(habit.category)

    # If we didn't get enough due to category constraints, fill from remaining
    if len(selected) < 2:
        for score, habit in scored:
            if habit not in selected and len(selected) < MAX_DAILY_SUGGESTIONS:
                selected.append(habit)

    return selected


def _format_suggestions(completions: list) -> list:
    """Format completion records for the template."""
    result = []
    for c in completions:
        habit = c.micro_habit
        result.append({
            "id": habit.id,
            "completion_id": c.id,
            "text": habit.text,
            "category": habit.category,
            "completed": c.completed,
            "dismissed": c.dismissed,
        })
    return result


def seed_micro_habit_pool():
    """Populate the micro-habit pool with initial habits.

    Called once during setup. Safe to call multiple times — skips
    if habits already exist.
    """
    if MicroHabit.query.first():
        return  # Already seeded

    habits = [
        # Movement — suggest when steps are low or day is light
        MicroHabit(
            category="movement",
            text="Take a 10-minute walk.",
            requires_low_steps=True,
        ),
        MicroHabit(
            category="movement",
            text="Stand up and stretch for 2 minutes.",
            requires_busy_day=True,
        ),
        MicroHabit(
            category="movement",
            text="Walk to the end of the street and back.",
            requires_low_steps=True,
        ),
        MicroHabit(
            category="movement",
            text="Take the stairs instead of the lift today.",
        ),
        MicroHabit(
            category="movement",
            text="Walk during a phone call.",
            requires_busy_day=True,
        ),
        MicroHabit(
            category="movement",
            text="A short walk after lunch.",
            requires_light_day=True,
            requires_low_steps=True,
        ),

        # Nutrition — general, always relevant
        MicroHabit(
            category="nutrition",
            text="Fill half your plate with vegetables at the next meal.",
        ),
        MicroHabit(
            category="nutrition",
            text="Drink a glass of water before your first coffee.",
        ),
        MicroHabit(
            category="nutrition",
            text="Eat one piece of fruit today.",
        ),
        MicroHabit(
            category="nutrition",
            text="Skip the second serving — see if you're still hungry in 20 minutes.",
        ),
        MicroHabit(
            category="nutrition",
            text="Choose water over a sugary drink.",
        ),

        # Recovery — suggest after poor sleep or on busy days
        MicroHabit(
            category="recovery",
            text="Be in bed by 23:00 tonight.",
            requires_poor_sleep=True,
        ),
        MicroHabit(
            category="recovery",
            text="Put the phone down 30 minutes before sleep.",
            requires_poor_sleep=True,
        ),
        MicroHabit(
            category="recovery",
            text="Take 5 deep breaths right now.",
            requires_busy_day=True,
        ),
        MicroHabit(
            category="recovery",
            text="Step outside for 2 minutes of fresh air.",
            requires_busy_day=True,
        ),
        MicroHabit(
            category="recovery",
            text="No screens in the last hour before bed.",
            requires_poor_sleep=True,
        ),

        # Awareness — always relevant, builds the path
        MicroHabit(
            category="awareness",
            text="Log one meal honestly today.",
        ),
        MicroHabit(
            category="awareness",
            text="Notice what triggered a craving — just notice, no judgement.",
        ),
        MicroHabit(
            category="awareness",
            text="Check in with yourself: how do you feel right now?",
        ),
        MicroHabit(
            category="awareness",
            text="Before eating, pause and ask: am I hungry or just bored?",
        ),

        # Training (adapted) — suggest on non-training days
        MicroHabit(
            category="training",
            text="10 kettlebell swings.",
            requires_no_training=True,
            requires_light_day=True,
        ),
        MicroHabit(
            category="training",
            text="One set of push-ups.",
            requires_no_training=True,
        ),
        MicroHabit(
            category="training",
            text="5 minutes of stretching.",
            requires_no_training=True,
        ),
        MicroHabit(
            category="training",
            text="Plank for as long as you can — once.",
            requires_no_training=True,
        ),
    ]

    for habit in habits:
        db.session.add(habit)

    db.session.commit()
    logger.info(f"Seeded {len(habits)} micro-habits into the pool")
