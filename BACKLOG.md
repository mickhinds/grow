# Grow — Backlog

Last updated: 2026-04-08

## Done (this session)

- [x] Personal Access Token support for Oura (no more complex OAuth app setup)
- [x] Auto-migration (no more deleting database on schema changes)
- [x] Exercise/workout tracking (Oura sync + manual logging, weekly target)
- [x] Visual garden (CSS scene that grows with your progress)
- [x] Movement card with Oura activity data
- [x] Calendar-aware nudges (busy day, free gaps, light day suggestions)
- [x] Google Calendar integration (OAuth flow, multi-calendar, event sync)
- [x] Scandinavian minimalist theme (forest green, warm amber, steel blue)
- [x] "Had a sweet" reason field with expandable UI
- [x] Movement nudge after sweets (gentle, not punitive)
- [x] **Security audit & code review** (see results below)

---

## Security Audit Results (2026-04-08)

### Fixed

- **CSRF protection added** — All POST forms now include CSRF tokens via Flask-WTF. Previously no CSRF protection at all.
- **OAuth state validation** — OAuth flows now generate random state tokens and validate them on callback. Previously used hardcoded strings ("grow_auth", "grow_gcal"), making OAuth CSRF attacks possible.
- **Disconnect routes changed to POST** — `/auth/oura/disconnect` and `/auth/google/disconnect` now require POST (not GET), preventing accidental disconnects via link prefetch or img tags.
- **Security headers added** — `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`, and `Cache-Control` headers set on all responses.
- **Secret key file permissions** — `.secret_key` file now created with 0600 permissions (owner read/write only).
- **Input length validation** — Server-side max length limits on all settings form fields (tokens, names, credentials). HTML maxlength attributes added too.
- **Input range validation** — Step target (1000–50000), weight (30–300), training target (1–14) validated server-side.
- **IF time format validation** — Basic format check before saving.
- **OAuth error messages sanitized** — Error details from external providers no longer echoed to user in flash messages.
- **Google Calendar timezone fix** — Calendar event queries now use the user's timezone instead of UTC, preventing missed events at day boundaries.
- **.gitignore hardened** — Added `token.json`, `credentials.json`, `*.pyc`, `.DS_Store`.
- **Flask-WTF added to requirements.txt**

### Known / Accepted (for personal use)

- **No authentication** — App has no login. Anyone on the network can access. Acceptable for personal Pi behind Tailscale; must add auth before any commercial use.
- **Tokens stored in plaintext** — Oura PAT, OAuth tokens, Google tokens in plain SQLite. Acceptable behind Tailscale on a personal device; would need encryption at rest for multi-user.
- **Hardcoded user_id=1** — Every route assumes a single user. Architecture supports multi-user (foreign keys in place) but routes need refactoring.
- **No rate limiting** — All routes open to unlimited requests. Low risk on personal LAN.
- **Streak queries are N+1** — `_update_streaks()` does up to 365 individual DB queries. Works fine for single-user SQLite; would need optimization for scale.
- **`datetime.utcnow()` deprecated** — Should migrate to `datetime.now(timezone.utc)` when convenient.

---

## Infrastructure / Deployment

- [ ] **Raspberry Pi 5 setup** — Install OS, deploy Grow, set up systemd service for auto-start, configure cron job for 7 AM daily sync
- [ ] **Tailscale** — Install on Pi + phone + Mac for secure access from anywhere, real HTTPS certificates, no port forwarding
- [ ] **Caddy reverse proxy** — Run on Pi in front of Flask, handles HTTPS via Tailscale certs
- [ ] **Google Calendar redirect URI** — Update to Tailscale hostname once Pi is running
- [ ] **Backfill Oura history** — Run `python3 scripts/sync_oura.py --backfill` once Pi is set up to pull historical data
- [ ] **Oura API agreement** — Review compliance requirements for personal use
- [ ] **Install flask-wtf on Pi** — `pip install flask-wtf` (new dependency from security audit)

---

## UI / Design

- [ ] **Updated visuals** — The garden scene and cards are functional but basic. Richer illustrations, smoother animations, maybe a day/night cycle in the garden that matches real time
- [ ] **More coherent layout** — Currently many cards scattered on the dashboard. Group related items, reduce visual noise, consider a tabbed or swipeable card approach for mobile
- [ ] **Compact design** — Less scrolling needed on the morning view. Priority info above the fold, details available on tap/expand
- [ ] **Polish the Scandinavian theme** — Refine typography, spacing, and color balance. Consider subtle texture or grain for warmth

---

## Features

- [ ] **Guided setup / onboarding** — First-run wizard to set goals (target weight, training schedule, IF window), connect Oura, connect Google Calendar. Currently everything is manual in Settings
- [ ] **AI-powered analysis** — "What's keeping you stuck?" — analyze patterns across sleep, steps, IF adherence, sweet triggers, training consistency. Surface insights like "You tend to skip IF on days with 4+ meetings" or "Your sweet cravings peak on low-sleep days". **Plan: local AI model (Ollama with Llama or Mistral) running on the Raspberry Pi**, keeping all data private and offline.
- [ ] **Better Oura data overview** — Dedicated view showing trends: sleep score over time, step averages, HRV trends, readiness patterns. Currently only shows yesterday's snapshot
- [ ] **Conversational interface** — Instead of just cards and buttons, a more chat-like interaction. Morning check-in ("How are you feeling?"), contextual questions, encouragement that feels personal rather than generic
- [ ] **Sweet trigger patterns** — Analyze the "circumstance" notes over time and surface recurring themes (stress, social, time of day, specific situations)
- [ ] **Weekly motivation digest** — Once a week, show a summary of "chose not to" motivations alongside sweet circumstances. What strategies are working? When do you cave? This is gold for the AI analysis feature — feed these notes to the local model for personalized pattern insights.
- [ ] **Feed motivation/circumstance notes to AI** — Both the sweet reasons and skip motivations are key input for the AI-powered analysis. The local model (Ollama) could correlate these with sleep, calendar, steps data to surface actionable insights like "Walking helps you resist — you skip sweets 3x more often on 8k+ step days"

---

## Code Quality / Security

- [x] **Security audit** — Completed 2026-04-08. See "Security Audit Results" above.
- [x] **Code review** — Completed 2026-04-08. Fixes applied.
- [ ] **Post-backlog security re-audit** — Run another audit after all UI/feature backlog items are done
- [ ] Previous audit findings (all fixed): client secret in HTML form, missing .gitignore, debug=True in prod, hardcoded SECRET_KEY, unsanitized error logging

---

## Future / Commercial

- [ ] **Multi-user support** — Architecture is ready (user_id on all tables). Needs: registration, login, individual settings
- [ ] **Oura partnership exploration** — Potential as an Oura ecosystem app
- [ ] **Standalone web app** — Move from self-hosted Pi to a hosted service others can use
- [ ] **Long-term achievements** — Milestone rewards beyond level progression (30-day streaks, seasonal challenges, garden unlockables)
- [ ] **API endpoints** — JSON versions of dashboard data for a potential future native mobile app

---

## Notes

- Running locally on Mac (port 8080) until Pi is set up
- Google Calendar OAuth redirect must use localhost, not private IP
- Oura PAT doesn't expire — no maintenance needed
- Database auto-migrates on startup — safe to add new fields without data loss
- Local AI model for pattern analysis: Ollama is a good fit for Pi (runs Llama 3, Mistral, etc. locally). Can feed it aggregated data from the last 30 days and ask for pattern insights. No data leaves the device.
