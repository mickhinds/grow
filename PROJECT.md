# Grow — Project Context

> A personal health and weight-loss app with a gamified living garden.
> Built by Micke. Started April 2026.

## What is Grow?

Grow combines Oura Ring data with sustainable weight loss habits into a mobile-friendly web app. Every good choice — hitting step targets, maintaining your fasting window, sleeping well, training, being aware of sweet cravings — earns seeds. Seeds grow a visual garden. The garden is you.

The philosophy is gentle, not punitive. Opportunity, not debt. Awareness counts.

## The Person

- **Micke** — single user for now, architecture supports multi-user
- Goal: lose ~25 kg using sustainable habits
- 16:8 intermittent fasting (11:00–19:00 eating window)
- 2x/week kettlebell training (Tue + Thu), sometimes boxing, cycling, garden work
- Oura Ring for sleep, activity, readiness tracking
- Google Calendar (work + personal) for context-aware nudges
- Runs on Mac (dev) → Raspberry Pi 5 (production, pending)

## Tech Stack

- **Backend**: Python 3.12, Flask 3.1, SQLAlchemy, SQLite
- **Frontend**: Jinja2 templates, vanilla CSS + JS, mobile-first
- **APIs**: Oura API v2 (PAT auth), Google Calendar API (OAuth2 read-only)
- **Security**: Flask-WTF CSRF, security headers, OAuth state validation
- **Deployment**: Currently `python wsgi.py` on Mac:8080. Planned: Raspberry Pi 5 + Tailscale + Caddy

## File Structure

```
grow/
├── wsgi.py                  # Entry point (python wsgi.py)
├── config.py                # Config class, auto-generated SECRET_KEY
├── requirements.txt         # Flask, Flask-WTF, SQLAlchemy, requests, gunicorn
├── BACKLOG.md               # Feature backlog and audit results
├── PROJECT.md               # This file
├── .gitignore               # .env, *.db, .secret_key, venv, *.pem, etc.
│
├── app/
│   ├── __init__.py          # App factory, CSRF, security headers, blueprints
│   ├── models.py            # All SQLAlchemy models (User, OuraDaily, Workout, etc.)
│   ├── migrate.py           # Auto-migration: adds missing columns on startup
│   │
│   ├── routes/
│   │   ├── dashboard.py     # Main dashboard, auto-sync, manual sync, nudges
│   │   ├── auth.py          # OAuth flows (Oura + Google), settings, disconnect
│   │   └── tracking.py      # Weight, IF, food/sweet, exercise logging
│   │
│   ├── services/
│   │   ├── oura_client.py   # Oura API v2 wrapper (PAT + OAuth, all endpoints)
│   │   ├── google_calendar.py # Google Calendar client + analyze_day()
│   │   ├── garden_engine.py # Seed calculation, level progression, streaks
│   │   └── data_sync.py     # Daily sync job (for cron), backfill utility
│   │
│   ├── templates/
│   │   ├── base.html        # Layout, bottom nav (Home, IF, Exercise, Log, Settings)
│   │   ├── dashboard.html   # Garden visual, Oura stats, IF, exercise, quick log
│   │   ├── settings.html    # Oura PAT, Google Calendar, profile, targets
│   │   ├── exercise.html    # Workout logging form + history
│   │   ├── if_log.html      # IF adherence logging
│   │   ├── food_log.html    # Sweet/snack logging with expandable reason fields
│   │   ├── weight.html      # Weight + waist tracking
│   │   ├── google_calendars.html  # Calendar selection checkboxes
│   │   └── auth_status.html # Debug: connection status
│   │
│   └── static/css/
│       └── style.css        # Scandinavian minimalist theme
│
├── scripts/
│   ├── sync_oura.py         # CLI sync script (for cron on Pi)
│   └── init_db.py           # DB initialization helper
│
├── data/                    # SQLite database lives here (gitignored)
└── tests/
```

## Database Models

All tables have `user_id` foreign key for future multi-user support.

- **User** — profile, goals, IF window, Oura PAT/OAuth tokens, Google tokens, calendar IDs
- **OuraDaily** — daily metrics: steps, calories, sleep score/duration/phases, readiness, HRV, HR, stress, SpO2
- **Workout** — exercise sessions (source: "oura" or "manual"), activity type, duration, intensity
- **WeightTracking** — weight + optional waist measurement
- **IFSession** — daily IF adherence log
- **FoodLog** — sweet/snack entries, "chose not to" flag, circumstance notes, motivation notes
- **GardenState** — current garden: total seeds, level, element growth (meadow/oak/pond/stones/path), streaks
- **GardenHistory** — daily seed breakdown (audit trail of every good choice)
- **CalendarEvent** — cached today's calendar events for nudge analysis
- **Notification** — nudges and insights

## Garden Gamification

Five garden elements, each grown by a different habit:

| Element  | Habit          | Seeds per day |
|----------|----------------|---------------|
| Meadow   | Steps/movement | 3–4           |
| Oak      | IF adherence   | 1–3           |
| Pond     | Sleep quality  | 2–3           |
| Stones   | Training       | 4–5           |
| Path     | Awareness      | 1–2           |

Good day: ~8–12 seeds. Lazy day: ~3–5. Level thresholds are cumulative.
7-day streak bonus: +5 seeds. The CSS visual garden grows proportionally.

## Key Design Decisions

1. **PAT over OAuth for personal use** — Oura Personal Access Token is the primary auth. Much simpler than registering an OAuth app. OAuth kept for future commercial use.

2. **Auto-migration** — `migrate.py` compares SQLAlchemy models to actual SQLite tables on startup and issues ALTER TABLE for missing columns. No more "delete the database" when adding fields.

3. **Auto-sync on dashboard load** — Oura data syncs automatically when you open the dashboard (if today's data is missing). Also has a manual "Sync" button. Designed to work without cron until Pi is set up.

4. **Gentle nudges** — Movement and sweet nudges are framed as opportunity, not punishment. "A walk would keep your garden growing" not "You ate a sweet, you need to exercise." Calendar-aware: busy days get empathy, light days get suggestions.

5. **Expandable quick-log UI** — "Chose not to" and "Had a sweet" buttons expand to optional text fields. Motivation for skipping ("What helped you say no?") and circumstance for sweets ("Do you want to share the circumstance?"). Both fields are optional — you can skip and just log.

6. **Scandinavian minimalist theme** — Deep forest green (#3d6b4f), warm amber (#c47a2a), steel blue (#5b7d95). Warm linen background, soft shadows, generous radius. Mobile-first.

7. **Google Calendar on localhost only** — Google OAuth doesn't allow redirect to private IPs. Auth done from Mac's localhost:8080, tokens stored in DB, phone reads them. Will switch to Tailscale hostname on Pi.

## Security (audited 2026-04-08)

- CSRF protection on all forms (Flask-WTF)
- OAuth state tokens (random, validated on callback)
- Security headers (X-Frame-Options, X-Content-Type-Options, etc.)
- Disconnect routes require POST
- Input length/range validation server-side
- .secret_key file: 0600 permissions
- No auth on routes (acceptable behind Tailscale, must add for commercial)
- Tokens in plaintext SQLite (acceptable for personal device)

## Current State (April 2026)

Working and usable:
- Dashboard with garden visual, Oura stats, IF tracking, exercise tracking
- Auto-sync from Oura on page load
- Manual sync button
- Sweet logging with expandable reason/circumstance field
- Skip logging with expandable motivation field
- Google Calendar integration with context-aware nudges
- Weight tracking with trend display
- Settings page with Oura PAT, Google Calendar, profile, targets

Not yet done (see BACKLOG.md):
- Raspberry Pi deployment + Tailscale
- Oura history backfill
- Updated visuals and UI layout
- Guided onboarding
- AI analysis (planned: Ollama with Llama/Mistral on Pi)
- Sweet trigger pattern analysis
- Weekly motivation digest
- Better Oura data trends view
- Conversational interface
