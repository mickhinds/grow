"""OAuth2 routes for Oura and Google Calendar."""

import time
import secrets
from urllib.parse import urlencode

import requests
from flask import (
    Blueprint, redirect, request, url_for, flash,
    current_app, render_template, session,
)
from markupsafe import escape

from app.models import db, User

bp = Blueprint("auth", __name__, url_prefix="/auth")

# Max lengths for form inputs
MAX_TOKEN_LEN = 2000
MAX_NAME_LEN = 100
MAX_CLIENT_ID_LEN = 300
MAX_CLIENT_SECRET_LEN = 200


def _get_oura_credentials():
    """Get Oura client credentials — database first, .env fallback."""
    user = db.session.get(User, 1)
    client_id = user.oura_client_id or current_app.config.get("OURA_CLIENT_ID", "")
    client_secret = user.oura_client_secret or current_app.config.get("OURA_CLIENT_SECRET", "")
    return client_id, client_secret


def _generate_state(provider: str) -> str:
    """Generate a random OAuth state token and store it in the session."""
    state = secrets.token_urlsafe(32)
    session[f"oauth_state_{provider}"] = state
    return state


def _validate_state(provider: str) -> bool:
    """Validate and consume the OAuth state token."""
    expected = session.pop(f"oauth_state_{provider}", None)
    actual = request.args.get("state", "")
    if not expected or not actual:
        return False
    return secrets.compare_digest(expected, actual)


@bp.route("/oura")
def oura_start():
    """Start Oura OAuth2 flow."""
    client_id, client_secret = _get_oura_credentials()

    if not client_id:
        flash("Set up your Oura API credentials in Settings first.", "error")
        return redirect(url_for("auth.settings"))

    state = _generate_state("oura")

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": url_for("auth.oura_callback", _external=True),
        "scope": "daily heartrate workout session personal spo2",
        "state": state,
    }
    auth_url = f"{current_app.config['OURA_AUTH_URL']}?{urlencode(params)}"
    return redirect(auth_url)


@bp.route("/oura/callback")
def oura_callback():
    """Handle Oura OAuth2 callback."""
    # Validate state to prevent CSRF
    if not _validate_state("oura"):
        flash("Invalid OAuth state. Please try connecting again.", "error")
        return redirect(url_for("auth.settings"))

    error = request.args.get("error")
    if error:
        flash("Oura authorization was denied or failed.", "error")
        return redirect(url_for("dashboard.index"))

    code = request.args.get("code")
    if not code:
        flash("No authorization code received.", "error")
        return redirect(url_for("dashboard.index"))

    # Exchange code for tokens
    client_id, client_secret = _get_oura_credentials()
    resp = requests.post(
        current_app.config["OURA_TOKEN_URL"],
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": url_for("auth.oura_callback", _external=True),
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )

    if resp.status_code != 200:
        flash("Token exchange failed. Please try again.", "error")
        return redirect(url_for("dashboard.index"))

    data = resp.json()

    # Store tokens
    user = db.session.get(User, 1)
    user.oura_access_token = data["access_token"]
    user.oura_refresh_token = data.get("refresh_token")
    user.oura_token_expires_at = time.time() + data.get("expires_in", 86400)
    db.session.commit()

    flash("Oura connected successfully!", "success")
    return redirect(url_for("dashboard.index"))


@bp.route("/oura/disconnect", methods=["POST"])
def oura_disconnect():
    """Remove Oura tokens (PAT and OAuth)."""
    user = db.session.get(User, 1)
    user.oura_pat = None
    user.oura_access_token = None
    user.oura_refresh_token = None
    user.oura_token_expires_at = None
    db.session.commit()

    flash("Oura disconnected.", "info")
    return redirect(url_for("auth.settings"))


# --- Google Calendar OAuth2 ---

def _get_google_credentials():
    """Get Google client credentials — database first, .env fallback."""
    user = db.session.get(User, 1)
    client_id = user.google_client_id or current_app.config.get("GOOGLE_CLIENT_ID", "")
    client_secret = user.google_client_secret or current_app.config.get("GOOGLE_CLIENT_SECRET", "")
    return client_id, client_secret


@bp.route("/google")
def google_start():
    """Start Google OAuth2 flow."""
    client_id, _ = _get_google_credentials()

    if not client_id:
        flash("Set up your Google API credentials in Settings first.", "error")
        return redirect(url_for("auth.settings"))

    state = _generate_state("google")

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": url_for("auth.google_callback", _external=True),
        "scope": current_app.config.get("GOOGLE_SCOPES", "https://www.googleapis.com/auth/calendar.readonly"),
        "access_type": "offline",
        "prompt": "consent",  # Always ask — ensures we get a refresh token
        "state": state,
    }
    auth_url = f"{current_app.config['GOOGLE_AUTH_URL']}?{urlencode(params)}"
    return redirect(auth_url)


@bp.route("/google/callback")
def google_callback():
    """Handle Google OAuth2 callback."""
    # Validate state to prevent CSRF
    if not _validate_state("google"):
        flash("Invalid OAuth state. Please try connecting again.", "error")
        return redirect(url_for("auth.settings"))

    error = request.args.get("error")
    if error:
        flash("Google authorization was denied or failed.", "error")
        return redirect(url_for("auth.settings"))

    code = request.args.get("code")
    if not code:
        flash("No authorization code received.", "error")
        return redirect(url_for("auth.settings"))

    client_id, client_secret = _get_google_credentials()
    resp = requests.post(
        current_app.config["GOOGLE_TOKEN_URL"],
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": url_for("auth.google_callback", _external=True),
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )

    if resp.status_code != 200:
        flash("Google token exchange failed. Please try again.", "error")
        return redirect(url_for("auth.settings"))

    data = resp.json()

    user = db.session.get(User, 1)
    user.google_access_token = data["access_token"]
    user.google_refresh_token = data.get("refresh_token")
    user.google_token_expires_at = time.time() + data.get("expires_in", 3600)
    db.session.commit()

    flash("Google Calendar connected! Go to Settings to choose which calendars to sync.", "success")
    return redirect(url_for("auth.google_calendars"))


@bp.route("/google/calendars")
def google_calendars():
    """Show available calendars for selection."""
    user = db.session.get(User, 1)
    if not user.google_access_token:
        flash("Connect Google Calendar first.", "error")
        return redirect(url_for("auth.settings"))

    from app.services.google_calendar import GoogleCalendarClient, GoogleCalendarError
    try:
        client = GoogleCalendarClient(current_app.config, user_id=1)
        calendars = client.list_calendars()
    except GoogleCalendarError:
        flash("Error loading calendars. Please try reconnecting.", "error")
        calendars = []

    selected = set((user.google_calendar_ids or "").split(","))

    return render_template("google_calendars.html", calendars=calendars, selected=selected, user=user)


@bp.route("/google/calendars", methods=["POST"])
def google_calendars_save():
    """Save selected calendars."""
    user = db.session.get(User, 1)
    selected = request.form.getlist("calendars")
    user.google_calendar_ids = ",".join(selected)
    db.session.commit()

    # Do an initial sync of today
    from app.services.google_calendar import GoogleCalendarClient
    try:
        client = GoogleCalendarClient(current_app.config, user_id=1)
        from datetime import date
        events = client.sync_events(date.today())
        flash(f"Calendars saved. Synced {len(events)} events for today.", "success")
    except Exception:
        flash("Calendars saved, but sync failed. It will retry on next load.", "error")

    return redirect(url_for("auth.settings"))


@bp.route("/google/disconnect", methods=["POST"])
def google_disconnect():
    """Remove Google tokens."""
    user = db.session.get(User, 1)
    user.google_access_token = None
    user.google_refresh_token = None
    user.google_token_expires_at = None
    user.google_calendar_ids = None
    db.session.commit()

    flash("Google Calendar disconnected.", "info")
    return redirect(url_for("auth.settings"))


@bp.route("/settings", methods=["GET"])
def settings():
    """Settings page — Oura credentials, profile, preferences."""
    user = db.session.get(User, 1)
    return render_template("settings.html", user=user)


@bp.route("/settings", methods=["POST"])
def settings_save():
    """Save settings."""
    user = db.session.get(User, 1)

    # Oura Personal Access Token (primary method)
    oura_pat = request.form.get("oura_pat", "").strip()[:MAX_TOKEN_LEN]
    if oura_pat:
        user.oura_pat = oura_pat

    # Oura OAuth credentials (advanced)
    oura_client_id = request.form.get("oura_client_id", "").strip()[:MAX_CLIENT_ID_LEN]
    oura_client_secret = request.form.get("oura_client_secret", "").strip()[:MAX_CLIENT_SECRET_LEN]
    if oura_client_id:
        user.oura_client_id = oura_client_id
    if oura_client_secret:
        user.oura_client_secret = oura_client_secret

    # Google Calendar credentials
    google_client_id = request.form.get("google_client_id", "").strip()[:MAX_CLIENT_ID_LEN]
    google_client_secret = request.form.get("google_client_secret", "").strip()[:MAX_CLIENT_SECRET_LEN]
    if google_client_id:
        user.google_client_id = google_client_id
    if google_client_secret:
        user.google_client_secret = google_client_secret

    # Profile
    name = request.form.get("name", "").strip()[:MAX_NAME_LEN]
    if name:
        user.name = name

    # IF window — validate format
    if_start = request.form.get("if_start", "").strip()
    if_end = request.form.get("if_end", "").strip()
    if if_start and len(if_start) == 5 and ":" in if_start:
        user.if_start = if_start
    if if_end and len(if_end) == 5 and ":" in if_end:
        user.if_end = if_end

    # Targets — validate ranges
    step_target = request.form.get("step_target", "").strip()
    if step_target:
        try:
            val = int(step_target)
            if 1000 <= val <= 50000:
                user.step_target = val
        except ValueError:
            pass

    target_weight = request.form.get("target_weight", "").strip()
    if target_weight:
        try:
            val = float(target_weight)
            if 30 <= val <= 300:
                user.target_weight_kg = val
        except ValueError:
            pass

    weekly_training = request.form.get("weekly_training_target", "").strip()
    if weekly_training:
        try:
            val = int(weekly_training)
            if 1 <= val <= 14:
                user.weekly_training_target = val
        except ValueError:
            pass

    db.session.commit()
    flash("Settings saved.", "success")
    return redirect(url_for("auth.settings"))


@bp.route("/status")
def status():
    """Show connection status — useful for debugging."""
    user = db.session.get(User, 1)
    return render_template("auth_status.html", user=user)
