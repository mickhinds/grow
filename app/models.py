"""Database models for Grow.

Every table includes user_id for future multi-user support.
For the personal prototype, user_id=1 everywhere.
"""

from datetime import datetime, date, time
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """User profile — single user for now, multi-user ready."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200))
    timezone = db.Column(db.String(50), default="Europe/Helsinki")

    # Goals
    target_weight_kg = db.Column(db.Float)
    starting_weight_kg = db.Column(db.Float)

    # IF preferences
    if_start = db.Column(db.String(5), default="11:00")
    if_end = db.Column(db.String(5), default="19:00")

    # Activity targets
    step_target = db.Column(db.Integer, default=8000)
    sleep_target_mins = db.Column(db.Integer, default=420)
    weekly_training_target = db.Column(db.Integer, default=2)  # Sessions per week

    # Oura — Personal Access Token (simple, for own data)
    oura_pat = db.Column(db.Text)

    # Oura — OAuth2 credentials (for multi-user / commercial)
    oura_client_id = db.Column(db.String(200))
    oura_client_secret = db.Column(db.String(200))

    # Oura — OAuth2 tokens (set automatically via OAuth flow)
    oura_access_token = db.Column(db.Text)
    oura_refresh_token = db.Column(db.Text)
    oura_token_expires_at = db.Column(db.Float)  # Unix timestamp

    # Google Calendar
    google_client_id = db.Column(db.String(300))
    google_client_secret = db.Column(db.String(200))
    google_access_token = db.Column(db.Text)
    google_refresh_token = db.Column(db.Text)
    google_token_expires_at = db.Column(db.Float)
    google_calendar_ids = db.Column(db.Text)  # Comma-separated calendar IDs to watch

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class OuraDaily(db.Model):
    """Daily metrics synced from Oura API. One row per user per day."""

    __tablename__ = "oura_daily"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)

    # Activity
    steps = db.Column(db.Integer)
    calories_burned = db.Column(db.Float)
    met_minutes_total = db.Column(db.Integer)
    met_minutes_high = db.Column(db.Integer)
    active_calories = db.Column(db.Integer)
    activity_score = db.Column(db.Integer)

    # Sleep
    sleep_score = db.Column(db.Integer)
    total_sleep_mins = db.Column(db.Integer)
    deep_sleep_mins = db.Column(db.Integer)
    rem_sleep_mins = db.Column(db.Integer)
    light_sleep_mins = db.Column(db.Integer)
    sleep_efficiency = db.Column(db.Float)

    # Readiness
    readiness_score = db.Column(db.Integer)
    hrv_daily = db.Column(db.Float)
    body_temp_deviation = db.Column(db.Float)
    recovery_index = db.Column(db.Integer)

    # Heart rate
    avg_heart_rate = db.Column(db.Integer)
    resting_heart_rate = db.Column(db.Integer)

    # Stress
    stress_high_mins = db.Column(db.Integer)
    recovery_high_mins = db.Column(db.Integer)

    # SpO2
    spo2_percentage = db.Column(db.Float)

    synced_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "date", name="uq_oura_user_date"),
    )


class WeightTracking(db.Model):
    """Weight entries — typically monthly."""

    __tablename__ = "weight_tracking"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    weight_kg = db.Column(db.Float, nullable=False)
    waist_cm = db.Column(db.Float)  # Optional waist measurement
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class IFSession(db.Model):
    """Intermittent fasting daily log."""

    __tablename__ = "if_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(5))  # "11:00"
    end_time = db.Column(db.String(5))  # "19:00"
    adherence = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "date", name="uq_if_user_date"),
    )


class FoodLog(db.Model):
    """Optional sweet/snack tracking."""

    __tablename__ = "food_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(5))  # "15:00"
    category = db.Column(db.String(50))  # sweet, snack, meal, drink
    description = db.Column(db.String(200))  # "cookie with coffee"
    chose_not_to = db.Column(db.Boolean, default=False)  # Logged a conscious skip
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Workout(db.Model):
    """Exercise sessions — synced from Oura or logged manually."""

    __tablename__ = "workouts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(5))  # "17:00"
    duration_mins = db.Column(db.Integer)
    activity_type = db.Column(db.String(100))  # kettlebell, boxing, cycling, gardening...
    source = db.Column(db.String(20), default="manual")  # "oura" or "manual"
    calories = db.Column(db.Integer)
    avg_heart_rate = db.Column(db.Integer)
    intensity = db.Column(db.String(20))  # low, medium, high (derived from HR or MET)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "date", "start_time", "activity_type",
                            name="uq_workout_user_date_time_type"),
    )


class GardenState(db.Model):
    """Current garden state per user."""

    __tablename__ = "garden_state"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)

    total_seeds = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)

    # Element growth levels (0-100 scale)
    meadow_growth = db.Column(db.Integer, default=0)  # Movement
    oak_growth = db.Column(db.Integer, default=0)  # IF
    pond_growth = db.Column(db.Integer, default=0)  # Sleep
    stones_growth = db.Column(db.Integer, default=0)  # Training
    path_growth = db.Column(db.Integer, default=0)  # Awareness

    # Streaks
    if_streak_days = db.Column(db.Integer, default=0)
    step_streak_days = db.Column(db.Integer, default=0)
    sleep_streak_days = db.Column(db.Integer, default=0)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class GardenHistory(db.Model):
    """Daily seed breakdown — the record of every good choice."""

    __tablename__ = "garden_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)

    # Seed breakdown
    seeds_steps = db.Column(db.Integer, default=0)
    seeds_if = db.Column(db.Integer, default=0)
    seeds_sleep = db.Column(db.Integer, default=0)
    seeds_training = db.Column(db.Integer, default=0)
    seeds_awareness = db.Column(db.Integer, default=0)
    seeds_micro_habits = db.Column(db.Integer, default=0)  # Micro-habit completions
    seeds_bonus = db.Column(db.Integer, default=0)  # Streaks, etc.
    seeds_total = db.Column(db.Integer, default=0)

    notes = db.Column(db.Text)  # Generated insight for the day
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "date", name="uq_garden_user_date"),
    )


class MicroHabit(db.Model):
    """Pool of available micro-habits — the smallest meaningful actions."""

    __tablename__ = "micro_habits"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)  # movement, nutrition, recovery, awareness, training
    text = db.Column(db.String(300), nullable=False)  # "Take a 10-minute walk"
    active = db.Column(db.Boolean, default=True)  # Can be disabled without deleting

    # Rule-based selection hints
    requires_low_steps = db.Column(db.Boolean, default=False)  # Suggest when steps are low
    requires_poor_sleep = db.Column(db.Boolean, default=False)  # Suggest after bad sleep
    requires_no_training = db.Column(db.Boolean, default=False)  # Suggest on non-training days
    requires_busy_day = db.Column(db.Boolean, default=False)  # Suggest on heavy calendar days
    requires_light_day = db.Column(db.Boolean, default=False)  # Suggest on free days

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MicroHabitCompletion(db.Model):
    """Daily micro-habit suggestions and completions."""

    __tablename__ = "micro_habit_completions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    micro_habit_id = db.Column(db.Integer, db.ForeignKey("micro_habits.id"), nullable=False)
    suggested = db.Column(db.Boolean, default=True)  # Was this suggested today?
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    dismissed = db.Column(db.Boolean, default=False)  # User chose to skip

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    micro_habit = db.relationship("MicroHabit", backref="completions")

    __table_args__ = (
        db.UniqueConstraint("user_id", "date", "micro_habit_id",
                            name="uq_micro_user_date_habit"),
    )


class CalendarEvent(db.Model):
    """Cached calendar events for today/tomorrow — refreshed on each sync."""

    __tablename__ = "calendar_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    calendar_id = db.Column(db.String(300))  # Which calendar
    calendar_name = db.Column(db.String(200))  # "Work" or "Personal"
    event_id = db.Column(db.String(300))  # Google event ID
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(5))  # "09:00" (None = all-day)
    end_time = db.Column(db.String(5))    # "10:00"
    summary = db.Column(db.String(500))
    is_all_day = db.Column(db.Boolean, default=False)
    synced_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    """Nudges and insights shown on the dashboard."""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    type = db.Column(db.String(50))  # movement, fasting, sleep, sweet, insight, garden
    message = db.Column(db.Text, nullable=False)
    shown = db.Column(db.Boolean, default=False)
    dismissed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def init_default_user(app):
    """Create default user for personal prototype."""
    with app.app_context():
        user = User.query.first()
        if not user:
            user = User(
                id=1,
                name="Micke",
                timezone=app.config.get("TIMEZONE", "Europe/Helsinki"),
                if_start=app.config.get("DEFAULT_IF_START", "11:00"),
                if_end=app.config.get("DEFAULT_IF_END", "19:00"),
                step_target=app.config.get("DEFAULT_STEP_TARGET", 8000),
                sleep_target_mins=app.config.get("DEFAULT_SLEEP_TARGET_MINS", 420),
            )
            db.session.add(user)

            garden = GardenState(user_id=1)
            db.session.add(garden)

            db.session.commit()
