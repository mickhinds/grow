# Grow — Backlog

Last updated: 2026-05-24

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
- [x] **Raspberry Pi 5 deployment** — OS installed, app deployed, systemd service running, SSH key auth configured
- [x] **GitHub repo** — https://github.com/mickhinds/grow (public)
- [x] **Concept document v2** — Full redesign around three phases, curious tone, micro-habits, plate model, local AI (see CONCEPT.md)
- [x] **Contextual greeting** — Time-of-day + data-informed greeting (sleep quality, readiness, calendar density). No more hardcoded "Good morning".
- [x] **Reset / Start Over system** — Three levels in Settings: Recalibrate (day counter only), Start Over (zero seeds/garden, keep data), Total Reset (wipe everything). Day counter now based on user.start_date.
- [x] **Disruption tracking** — Structured disruption logging: injury (body part, can-still-do, avoid), work stress, illness, travel, mental health. Status lifecycle: active → adapting → recovering → resolved. Dashboard banner for active disruptions.
- [x] **Dashboard redesign** — Garden-hero morning view, status sentence, weekly focus system, progressive disclosure ("More details"), anomaly-only metric cards. See CONCEPT.md section 9.
- [x] **Status sentence engine** — Rule-based one-liner from yesterday's data, today's context, active disruptions, and weekly focus. AI-composable slot for Ministral 3B.
- [x] **Weekly focus system** — User picks weekly priority from data-informed suggestions. Focus shapes status sentence and dashboard emphasis.
- [x] **Anomaly detection** — Metrics surface on dashboard only when they deviate from personal 14-day rolling average. Covers sleep, steps, RHR, readiness, HRV.

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

- [x] **Raspberry Pi 5 setup** — Deployed on hallonpaj1 (192.168.50.16:8080), systemd service, SSH key auth
- [x] **GitHub repo** — https://github.com/mickhinds/grow (public, .gitignore protects secrets)
- [x] **Install flask-wtf on Pi** — Done as part of Pi deployment
- [x] **Tailscale** — Installed on Pi + Pixel + Mac. Secure access from anywhere via hallonpaj1.tail745dc7.ts.net
- [x] **Caddy reverse proxy** — Running on Pi in front of Flask, HTTPS via Tailscale certs
- [ ] **Google Calendar redirect URI** — Update to Tailscale hostname (hallonpaj1.tail745dc7.ts.net)
- [ ] **Backfill Oura history** — Run `python3 scripts/sync_oura.py --backfill` to pull historical data
- [ ] **Oura API agreement** — Review compliance requirements for personal use
- [ ] **Install Ollama on Pi** — Local AI runtime for Ministral 3B (see CONCEPT.md section 9)
- [x] **Web Push notifications** — Service worker + VAPID keys + push subscription + cron scripts. 9 AM morning nudge if no dashboard activity, inactivity nudge after 2+ days. Requires `pip install pywebpush cryptography` on Pi + VAPID keys in .env.
- [ ] **Cron job for daily sync** — 7 AM daily Oura sync via `scripts/sync_oura.py`
- [ ] **Cron job for push notifications** — 9 AM morning nudge, 8 PM inactivity check via `scripts/send_push.py`

---

## Priority Fixes

- [ ] **Weight logging under Log tab** — Weight tracking should be accessible from the Log tab in bottom nav (alongside sweet/skip logging). Currently only reachable via "More details" on dashboard. Add weight entry + trend view to the Log page.

---

## UI / Design

- [x] **More coherent layout** — Dashboard redesigned: garden-hero + status sentence + focus + micro-habits + quick log above the fold. Details behind progressive disclosure.
- [x] **Compact design** — Morning view shows 5 elements max. Metrics only surface as anomaly cards when notable.
- [ ] **Updated visuals** — The garden scene is functional but basic. Richer illustrations, smoother animations, maybe a day/night cycle that matches real time or phase (spring/summer/autumn)
- [ ] **Polish the Scandinavian theme** — Refine typography, spacing, and color balance. Consider subtle texture or grain for warmth

---

## Concept v2 Features (see CONCEPT.md for full design)

### Phase System
- [ ] **Three-phase engine** — Build Routine → Harvest → Adapt. Phase detection based on consistency metrics and disruption events. Phase transitions with user confirmation.
- [ ] **Phase-aware UI** — Dashboard adapts to current phase: generous in Phase 1, trend-focused in Phase 2, gentle in Phase 3. Garden visual reflects phase (spring/summer/autumn).

### Micro-Habits
- [x] **Micro-habit system** — Daily suggestions (1–3) drawn from rule-based context-aware pool. Movement, nutrition, recovery, awareness, adapted training. Each earns 1 seed. Dedicated section on dashboard.
- [x] **Micro-habit database** — Pool of 24 micro-habits tagged by category and context flags (low steps, poor sleep, busy/light day, non-training day). Seeded on startup.
- [ ] **Phase-aware micro-habits** — Adjust suggestion pool and frequency based on current phase. More generous in Phase 1, supplement in Phase 2, anchor in Phase 3.
- [ ] **Disruption-adapted micro-habits** — Filter pool based on active disruptions (injury, stress). E.g., no kettlebell swings with knee injury.

### Nutrition
- [ ] **Plate model UI** — Simple meal proportion selector (tallriksmodellen). Four-tap interface: mostly balanced / heavy carbs / skipped vegetables / great plate.
- [ ] **Plate model tracking** — Store meal assessments, surface patterns over time via AI.

### Weekly Reflection
- [ ] **Weekly reflection engine** — Three-part structure: week in numbers (AI-selected highlights), smart questions (AI-generated from data), next week plan (calendar + patterns). Sunday evening or Monday morning.
- [ ] **Reflection storage** — Store answers, feed them back to AI for longitudinal patterns.

### Disruption Tracking
- [x] **Disruption logging** — Structured entry: injury (body part, severity, can-still-do, timeline), work stress (duration, impact areas), illness, travel. Creates timeline with reassessment points.
- [ ] **Adapted programs** — Auto-adjust targets based on disruption type. Reduced step goals, alternative exercises, micro-habits only mode.
- [ ] **Recovery arc** — Lifecycle: acute → adaptation → reintegration → resolved. Gradual return to Phase 1/2.

### AI / Local Intelligence
- [x] **Ollama + Ministral 3B setup** — Installed on Pi, running via Ollama with manually imported GGUF from HuggingFace (mistralai/Ministral-3-3B-Instruct-2512-GGUF, Q4_K_M). CPU-only, ~2 GB RAM.
- [x] **Two-agent architecture** — Analyst (structured JSON insights) + Voice (natural language message). Python orchestrator chains them. No LangChain — direct Ollama HTTP API. Rule-based fallback when Ollama is unavailable.
- [x] **Data compiler** — Pure Python module that gathers all data (Oura, calendar, IF, weight, garden, correlations) into structured JSON context for the LLM. Python does math, LLM interprets.
- [x] **Morning analysis pipeline** — Cron-driven script (06:00 daily). Syncs data → compiles context → Analyst → Voice → stores in AIInsight table. Dashboard reads pre-computed result.
- [x] **Weekly report pipeline** — Cron-driven (09:00 Sundays). Same architecture, different prompts. Shown on dashboard as "Week in review" card.
- [x] **AI insights on dashboard** — AI-composed status sentence with "AI" badge. Falls back to rule-based sentence if Ollama is down.
- [ ] **Prompt tuning** — Refine Analyst and Voice system prompts based on real output quality. Add Grow-specific vocabulary (garden, seeds, streaks) to Voice. Add few-shot examples.
- [ ] **Correlation insights** — Surface calendar-vs-sleep and calendar-vs-movement patterns via Analyst agent over 14-day windows.
- [ ] **Language support** — Add Swedish and Finnish as AI output languages for potential test users. Currently English only.

### Existing Features (carried forward)
- [ ] **Guided setup / onboarding** — First-run wizard for goals, Oura, Google Calendar
- [ ] **Better Oura data overview** — Trend views: sleep score, step averages, HRV, readiness over time
- [ ] **Sweet trigger patterns** — AI analysis of circumstance notes over time
- [ ] **Conversational interface** — Chat-like interaction (deferred, depends on local AI reliability)

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

- Running on Pi (hallonpaj1, 192.168.50.16:8080) via systemd. Mac used for development.
- Google Calendar OAuth redirect must use localhost on Mac, will switch to Tailscale hostname
- Oura PAT doesn't expire — no maintenance needed
- Database auto-migrates on startup — safe to add new fields without data loss
- Local AI: Ollama + Ministral 3B (Q4_K_M quantization) on Pi, 4 GB RAM. nomic-embed-text for embeddings, sqlite-vec for vector storage. All inference local, no data leaves device.
- Concept document v2 (CONCEPT.md) is the design ground for all new features
- Leading design principle: **the tone is curious**
