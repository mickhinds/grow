"""Tracking routes — weight, IF, food logging.

These are the manual inputs. Kept minimal: quick taps, not data entry.
"""

from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

from app.models import db, User, WeightTracking, IFSession, FoodLog, Workout, MicroHabitCompletion, Disruption
from app.services.garden_engine import update_garden
from app.services.micro_habits import complete_micro_habit, dismiss_micro_habit

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


# --- Micro-habits ---

@bp.route("/micro-habit/complete/<int:completion_id>", methods=["POST"])
def micro_habit_complete(completion_id):
    """Complete a micro-habit. Earns 1 seed."""
    completion = db.session.get(MicroHabitCompletion, completion_id)
    if not completion:
        flash("Micro-habit not found.", "error")
        return redirect(url_for("dashboard.index"))

    if complete_micro_habit(completion_id):
        flash("Done! +1 seed for showing up.", "success")
    else:
        flash("Already completed.", "info")

    return redirect(url_for("dashboard.index"))


@bp.route("/micro-habit/dismiss/<int:completion_id>", methods=["POST"])
def micro_habit_dismiss(completion_id):
    """Dismiss a micro-habit suggestion. No judgement."""
    if dismiss_micro_habit(completion_id):
        flash("Skipped — no worries.", "info")

    return redirect(url_for("dashboard.index"))


# --- Disruption tracking ---

DISRUPTION_TYPES = [
    ("injury", "Injury"),
    ("work_stress", "Work stress"),
    ("illness", "Illness"),
    ("travel", "Travel"),
    ("mental_health", "Mental health"),
    ("life_event", "Life event"),
    ("other", "Other"),
]


@bp.route("/disruptions")
def disruptions():
    """Disruption overview — active, past, and new entry."""
    active = Disruption.query.filter(
        Disruption.user_id == 1,
        Disruption.status.in_(["active", "adapting", "recovering"]),
    ).order_by(Disruption.created_at.desc()).all()

    resolved = Disruption.query.filter_by(
        user_id=1, status="resolved"
    ).order_by(Disruption.actual_end.desc()).limit(10).all()

    return render_template(
        "disruptions.html",
        active=active,
        resolved=resolved,
        disruption_types=DISRUPTION_TYPES,
        today=date.today(),
    )


@bp.route("/disruptions/add", methods=["POST"])
def disruption_add():
    """Log a new disruption."""
    disruption_type = request.form.get("disruption_type", "other").strip()
    title = request.form.get("title", "").strip()[:200]
    notes = request.form.get("notes", "").strip()
    severity_str = request.form.get("severity", "3")
    body_part = request.form.get("body_part", "").strip()[:100]
    can_still_do = request.form.get("can_still_do", "").strip()
    avoid = request.form.get("avoid", "").strip()
    estimated_end_str = request.form.get("estimated_end", "").strip()

    if not title:
        flash("Give the disruption a short title.", "error")
        return redirect(url_for("tracking.disruptions"))

    try:
        severity = max(1, min(5, int(severity_str)))
    except ValueError:
        severity = 3

    estimated_end = None
    if estimated_end_str:
        try:
            estimated_end = date.fromisoformat(estimated_end_str)
        except ValueError:
            pass

    # Impact flags
    affects_movement = "affects_movement" in request.form
    affects_training = "affects_training" in request.form
    affects_sleep = "affects_sleep" in request.form
    affects_nutrition = "affects_nutrition" in request.form

    disruption = Disruption(
        user_id=1,
        disruption_type=disruption_type,
        title=title,
        notes=notes if notes else None,
        severity=severity,
        body_part=body_part if body_part else None,
        can_still_do=can_still_do if can_still_do else None,
        avoid=avoid if avoid else None,
        affects_movement=affects_movement,
        affects_training=affects_training,
        affects_sleep=affects_sleep,
        affects_nutrition=affects_nutrition,
        start_date=date.today(),
        estimated_end=estimated_end,
        status="active",
    )
    db.session.add(disruption)
    db.session.commit()

    flash(f"Disruption logged: {title}. Your garden adapts.", "info")
    return redirect(url_for("tracking.disruptions"))


@bp.route("/disruptions/<int:disruption_id>/update", methods=["POST"])
def disruption_update(disruption_id):
    """Update disruption status."""
    disruption = db.session.get(Disruption, disruption_id)
    if not disruption:
        flash("Disruption not found.", "error")
        return redirect(url_for("tracking.disruptions"))

    new_status = request.form.get("status", "").strip()
    valid_statuses = ["active", "adapting", "recovering", "resolved"]
    if new_status not in valid_statuses:
        flash("Invalid status.", "error")
        return redirect(url_for("tracking.disruptions"))

    disruption.status = new_status
    if new_status == "resolved":
        disruption.actual_end = date.today()

    # Allow updating notes and severity
    notes = request.form.get("notes", "").strip()
    if notes:
        disruption.notes = notes

    severity_str = request.form.get("severity", "")
    if severity_str:
        try:
            disruption.severity = max(1, min(5, int(severity_str)))
        except ValueError:
            pass

    db.session.commit()
    flash(f"Updated: {disruption.title} → {new_status}.", "info")
    return redirect(url_for("tracking.disruptions"))
