"""Tracking routes — weight, IF, food logging.

These are the manual inputs. Kept minimal: quick taps, not data entry.
"""

from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

from app.models import db, User, WeightTracking, IFSession, FoodLog, Workout
from app.services.garden_engine import update_garden

bp = Blueprint("tracking", __name__)


# --- Weight ---

@bp.route("/weight", methods=["GET"])
def weight_form():
    """Weight logging form."""
    latest = WeightTracking.query.filter_by(user_id=1).order_by(
        WeightTracking.date.desc()
    ).first()

    history = WeightTracking.query.filter_by(user_id=1).order_by(
        WeightTracking.date.asc()
    ).all()

    return render_template("weight.html", latest=latest, history=history)


@bp.route("/weight", methods=["POST"])
def weight_log():
    """Log a weight entry."""
    weight_str = request.form.get("weight", "").strip()
    date_str = request.form.get("date", date.today().isoformat())
    waist_str = request.form.get("waist", "").strip()
    notes = request.form.get("notes", "").strip()

    # Validate weight
    try:
        weight_kg = float(weight_str)
        if not (40 <= weight_kg <= 200):
            flash("Weight should be between 40-200 kg.", "error")
            return redirect(url_for("tracking.weight_form"))
    except ValueError:
        flash("Enter a valid weight.", "error")
        return redirect(url_for("tracking.weight_form"))

    # Parse date
    try:
        entry_date = date.fromisoformat(date_str)
    except ValueError:
        entry_date = date.today()

    # Optional waist
    waist_cm = None
    if waist_str:
        try:
            waist_cm = float(waist_str)
        except ValueError:
            pass

    entry = WeightTracking(
        user_id=1,
        date=entry_date,
        weight_kg=weight_kg,
        waist_cm=waist_cm,
        notes=notes,
    )
    db.session.add(entry)
    db.session.commit()

    flash(f"Logged {weight_kg} kg.", "success")
    return redirect(url_for("dashboard.index"))


# --- IF tracking ---

@bp.route("/if", methods=["GET"])
def if_form():
    """IF logging form."""
    user = db.session.get(User, 1)
    today_session = IFSession.query.filter_by(user_id=1, date=date.today()).first()

    recent = IFSession.query.filter_by(user_id=1).order_by(
        IFSession.date.desc()
    ).limit(14).all()

    return render_template(
        "if_log.html", user=user, today_session=today_session, recent=recent
    )


@bp.route("/if", methods=["POST"])
def if_log():
    """Log IF adherence for today."""
    entry_date_str = request.form.get("date", date.today().isoformat())
    start_time = request.form.get("start_time", "11:00")
    end_time = request.form.get("end_time", "19:00")
    adherence = request.form.get("adherence") == "yes"
    notes = request.form.get("notes", "").strip()

    try:
        entry_date = date.fromisoformat(entry_date_str)
    except ValueError:
        entry_date = date.today()

    # Upsert
    existing = IFSession.query.filter_by(user_id=1, date=entry_date).first()
    if existing:
        existing.start_time = start_time
        existing.end_time = end_time
        existing.adherence = adherence
        existing.notes = notes
    else:
        session = IFSession(
            user_id=1,
            date=entry_date,
            start_time=start_time,
            end_time=end_time,
            adherence=adherence,
            notes=notes,
        )
        db.session.add(session)

    db.session.commit()

    # Recalculate garden for this day
    update_garden(1, entry_date)

    emoji = "+" if adherence else "~"
    flash(f"IF logged for {entry_date}. {emoji}", "success")
    return redirect(url_for("dashboard.index"))


@bp.route("/if/quick", methods=["POST"])
def if_quick_log():
    """Quick one-tap IF log (adherence=yes, default times)."""
    user = db.session.get(User, 1)
    today = date.today()

    existing = IFSession.query.filter_by(user_id=1, date=today).first()
    if not existing:
        session = IFSession(
            user_id=1,
            date=today,
            start_time=user.if_start,
            end_time=user.if_end,
            adherence=True,
        )
        db.session.add(session)
        db.session.commit()
        update_garden(1, today)
        flash("IF logged — on track!", "success")
    else:
        flash("Already logged today.", "info")

    return redirect(url_for("dashboard.index"))


# --- Food / sweet logging ---

@bp.route("/log", methods=["GET"])
def food_form():
    """Food/sweet logging form."""
    today_entries = FoodLog.query.filter_by(
        user_id=1, date=date.today()
    ).order_by(FoodLog.created_at.desc()).all()

    return render_template("food_log.html", entries=today_entries)


@bp.route("/log", methods=["POST"])
def food_log():
    """Log a food/sweet entry."""
    category = request.form.get("category", "sweet")
    description = request.form.get("description", "").strip()
    time_str = request.form.get("time", datetime.now().strftime("%H:%M"))
    chose_not_to = request.form.get("chose_not_to") == "yes"
    notes = request.form.get("notes", "").strip()

    entry = FoodLog(
        user_id=1,
        date=date.today(),
        time=time_str,
        category=category,
        description=description,
        chose_not_to=chose_not_to,
        notes=notes,
    )
    db.session.add(entry)
    db.session.commit()

    # Update garden
    update_garden(1, date.today())

    if chose_not_to:
        flash("Conscious choice logged. +2 seeds.", "success")
    else:
        flash("Logged. Awareness earns a seed.", "success")

    return redirect(url_for("dashboard.index"))


@bp.route("/log/quick-sweet", methods=["POST"])
def quick_sweet():
    """Quick sweet log with optional reason."""
    reason = request.form.get("reason", "").strip()
    description = reason if reason else request.form.get("what", "sweet")
    entry = FoodLog(
        user_id=1,
        date=date.today(),
        time=datetime.now().strftime("%H:%M"),
        category="sweet",
        description=description,
        notes=reason,
    )
    db.session.add(entry)
    db.session.commit()
    update_garden(1, date.today())
    flash("Sweet logged. +1 seed for awareness.", "success")
    return redirect(url_for("dashboard.index"))


@bp.route("/log/quick-skip", methods=["POST"])
def quick_skip():
    """Quick 'chose not to' log with optional motivation."""
    motivation = request.form.get("motivation", "").strip()[:300]
    entry = FoodLog(
        user_id=1,
        date=date.today(),
        time=datetime.now().strftime("%H:%M"),
        category="sweet",
        description="Chose not to",
        chose_not_to=True,
        notes=motivation if motivation else None,
    )
    db.session.add(entry)
    db.session.commit()
    update_garden(1, date.today())
    flash("Strong choice. +2 seeds.", "success")
    return redirect(url_for("dashboard.index"))


# --- Workout / Exercise logging ---

ACTIVITY_TYPES = [
    "Kettlebell", "Boxing", "Cycling", "Walking", "Running",
    "Swimming", "Yoga", "Garden work", "Other",
]


@bp.route("/exercise", methods=["GET"])
def exercise_form():
    """Exercise logging form + history."""
    recent = Workout.query.filter_by(user_id=1).order_by(
        Workout.date.desc()
    ).limit(20).all()

    # This week's count
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_count = Workout.query.filter(
        Workout.user_id == 1,
        Workout.date >= week_start,
    ).count()

    user = db.session.get(User, 1)

    return render_template(
        "exercise.html",
        recent=recent,
        week_count=week_count,
        target=user.weekly_training_target or 2,
        activity_types=ACTIVITY_TYPES,
    )


@bp.route("/exercise", methods=["POST"])
def exercise_log():
    """Log a workout manually."""
    activity_type = request.form.get("activity_type", "Other").strip()
    duration_str = request.form.get("duration", "").strip()
    date_str = request.form.get("date", date.today().isoformat())
    time_str = request.form.get("time", datetime.now().strftime("%H:%M"))
    intensity = request.form.get("intensity", "medium")
    notes = request.form.get("notes", "").strip()

    try:
        entry_date = date.fromisoformat(date_str)
    except ValueError:
        entry_date = date.today()

    duration_mins = None
    if duration_str:
        try:
            duration_mins = int(duration_str)
        except ValueError:
            pass

    workout = Workout(
        user_id=1,
        date=entry_date,
        start_time=time_str,
        duration_mins=duration_mins,
        activity_type=activity_type,
        intensity=intensity,
        source="manual",
        notes=notes,
    )
    db.session.add(workout)
    db.session.commit()

    update_garden(1, entry_date)

    flash(f"{activity_type} logged. +4 seeds for training!", "success")
    return redirect(url_for("dashboard.index"))


@bp.route("/exercise/quick", methods=["POST"])
def exercise_quick_log():
    """Quick one-tap workout log."""
    activity_type = request.form.get("activity_type", "Kettlebell")
    today = date.today()

    workout = Workout(
        user_id=1,
        date=today,
        start_time=datetime.now().strftime("%H:%M"),
        activity_type=activity_type,
        source="manual",
        intensity="medium",
    )
    db.session.add(workout)
    db.session.commit()

    update_garden(1, today)
    flash(f"{activity_type} session logged!", "success")
    return redirect(url_for("dashboard.index"))
