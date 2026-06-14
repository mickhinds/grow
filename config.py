import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent


def _get_or_create_secret_key():
    """Get secret key from .env, or generate and save one."""
    key = os.getenv("FLASK_SECRET_KEY")
    if key and key != "change_this_to_a_random_string":
        return key
    # Generate a persistent key stored in a local file
    key_file = BASE_DIR / ".secret_key"
    if key_file.exists():
        return key_file.read_text().strip()
    import secrets
    key = secrets.token_hex(32)
    key_file.write_text(key)
    key_file.chmod(0o600)  # Owner read/write only
    return key


class Config:
    SECRET_KEY = _get_or_create_secret_key()
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / os.getenv('DATABASE_PATH', 'data/grow.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Oura API
    OURA_CLIENT_ID = os.getenv("OURA_CLIENT_ID", "")
    OURA_CLIENT_SECRET = os.getenv("OURA_CLIENT_SECRET", "")
    OURA_AUTH_URL = "https://cloud.ouraring.com/oauth/authorize"
    OURA_TOKEN_URL = "https://cloud.ouraring.com/oauth/token"
    OURA_API_BASE = "https://api.ouraring.com/v2/usercollection"

    # Google Calendar
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
    GOOGLE_SCOPES = "https://www.googleapis.com/auth/calendar.readonly"

    # Web Push (VAPID) — generate keys with scripts/generate_vapid_keys.py
    VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
    VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
    VAPID_CLAIM_EMAIL = os.getenv("VAPID_CLAIM_EMAIL", "mailto:mikael.hindsberg@yle.fi")

    # Timezone
    TIMEZONE = os.getenv("TIMEZONE", "Europe/Helsinki")

    # Default user settings (personalized for Micke — becomes onboarding in commercial)
    DEFAULT_IF_START = "11:00"
    DEFAULT_IF_END = "19:00"
    DEFAULT_STEP_TARGET = 8000
    DEFAULT_SLEEP_TARGET_MINS = 420  # 7 hours

    # Training schedule (day_of_week: 0=Mon, 1=Tue, etc.)
    TRAINING_SCHEDULE = [
        {"day": 1, "time": "17:00", "duration": 60, "type": "Kettlebell"},  # Tuesday
        {"day": 3, "time": "07:30", "duration": 60, "type": "Kettlebell"},  # Thursday
    ]

    # Ollama (local LLM)
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "ministral-3b")
