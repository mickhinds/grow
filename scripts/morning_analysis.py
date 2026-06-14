#!/usr/bin/env python3
"""Morning AI analysis — run via cron daily at 06:00.

Runs the full pipeline:
  1. Sync fresh Oura data (yesterday)
  2. Sync Google Calendar (today)
  3. Compile all data into structured context
  4. Run Analyst → Voice agents via Ollama
  5. Store the result in AIInsight table
  6. Optionally send a push notification

If Ollama is unavailable, stores a rule-based fallback instead.
The dashboard always has something to show.

Usage:
    python scripts/morning_analysis.py           # Daily morning insight
    python scripts/morning_analysis.py --weekly   # Sunday weekly report
    python scripts/morning_analysis.py --dry-run  # Show what would be stored, don't save
    python scripts/morning_analysis.py --push     # Also send push notification

Crontab entries:
    # Morning insight at 06:00 every day
    0 6 * * * cd /home/mickfinn/grow && venv/bin/python scripts/morning_analysis.py --push >> logs/ai.log 2>&1

    # Weekly report at 09:00 every Sunday
    0 9 * * 0 cd /home/mickfinn/grow && venv/bin/python scripts/morning_analysis.py --weekly --push >> logs/ai.log 2>&1

Architecture notes (for Micke's learning):
    This script is the ORCHESTRATOR from our diagram. It's Python, not an LLM.
    It coordinates data gathering, LLM calls, and storage. If any step fails,
    the next step either gets a fallback or skips gracefully.

    Compare this to a LangChain "agent" that would:
    - Use an LLM to decide which tools to call (wasteful for a fixed pipeline)
    - Add 3-4 dependencies and 500+ lines of framework code
    - Be harder to debug because the control flow is inside the LLM

    Here, control flow is explicit Python. The LLM does what LLMs are good at:
    interpreting patterns and writing natural language. Python does everything else.
"""

import sys
import json
import argparse
import logging
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.models import db, User, AIInsight
from app.services.ollama_client import OllamaClient
from app.services.data_compiler import compile_user_context, compile_weekly_context
from app.services.ai_agents import generate_morning_insight, generate_weekly_report
from app.services.status_sentence import compose_status_sentence


def main():
    parser = argparse.ArgumentParser(description="Run AI analysis pipeline")
    parser.add_argument("--weekly", action="store_true", help="Generate weekly report instead of daily")
    parser.add_argument("--dry-run", action="store_true", help="Print result without saving to DB")
    parser.add_argument("--push", action="store_true", help="Send push notification with the insight")
    parser.add_argument("--date", type=str, help="Override date (YYYY-MM-DD), default: today")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("ai")

    app = create_app()

    with app.app_context():
        today = date.fromisoformat(args.date) if args.date else date.today()
        user = db.session.get(User, 1)

        if not user:
            logger.error("No user found")
            return 1

        # Step 1: Sync fresh data
        logger.info("Step 1: Syncing data...")
        _sync_data(user, today)

        # Step 2: Check if Ollama is available
        client = OllamaClient(
            base_url=app.config.get("OLLAMA_BASE_URL"),
            model=app.config.get("OLLAMA_MODEL"),
        )

        ollama_up = client.is_available()
        if ollama_up:
            logger.info(f"Ollama available, model: {client.model}")
        else:
            logger.info("Ollama not available — will use rule-based fallback")

        # Step 3: Run the pipeline
        if args.weekly:
            result = _run_weekly(user, today, client, ollama_up, logger)
        else:
            result = _run_daily(user, today, client, ollama_up, logger)

        if not result:
            logger.error("Pipeline produced no result")
            return 1

        # Step 4: Output / Store
        if args.dry_run:
            print("\n" + "=" * 60)
            print(f"{'WEEKLY' if args.weekly else 'DAILY'} — {today}")
            print("=" * 60)
            print(f"\nSource: {result['source']}")
            print(f"Message: {result['message']}")
            if result.get("insight") or result.get("analysis"):
                print(f"\nAnalysis: {json.dumps(result.get('insight') or result.get('analysis'), indent=2)}")
            print()
        else:
            _store_result(user, today, result, is_weekly=args.weekly)
            logger.info(f"Stored {'weekly' if args.weekly else 'morning'} insight")

            # Step 5: Push notification (optional)
            if args.push:
                _send_push(app, user, result, logger)

        return 0


def _run_daily(user, today, client, ollama_up, logger):
    """Run daily morning insight pipeline."""
    logger.info("Step 2: Compiling user context...")
    context = compile_user_context(user.id, today)

    if ollama_up:
        logger.info("Step 3: Running AI agents...")
        result = generate_morning_insight(context, client)

        if result:
            logger.info(f"AI insight: {result['message'][:80]}...")
            return result
        else:
            logger.warning("AI pipeline failed — falling back to rules")

    # Fallback: rule-based status sentence
    logger.info("Using rule-based status sentence")
    message = compose_status_sentence(user, today)
    return {
        "message": message,
        "insight": None,
        "source": "rules",
    }


def _run_weekly(user, today, client, ollama_up, logger):
    """Run weekly report pipeline."""
    logger.info("Step 2: Compiling weekly context...")
    context = compile_weekly_context(user.id, today)

    if ollama_up:
        logger.info("Step 3: Running weekly AI agents...")
        result = generate_weekly_report(context, client)

        if result:
            logger.info(f"Weekly report: {result['message'][:80]}...")
            return result
        else:
            logger.warning("Weekly AI pipeline failed — using summary")

    # Fallback: basic summary
    sleep_avg = context.get("sleep", {}).get("avg_score")
    steps_avg = context.get("movement", {}).get("avg_steps")
    workout_mins = context.get("movement", {}).get("total_workout_mins", 0)
    target = context.get("movement", {}).get("target_mins", 150)

    parts = []
    if sleep_avg:
        parts.append(f"Sleep averaged {sleep_avg:.0f}")
    if steps_avg:
        parts.append(f"steps {steps_avg:.0f}/day")
    if workout_mins > 0:
        parts.append(f"{workout_mins} of {target} activity minutes")
    message = "This week: " + ", ".join(parts) + "." if parts else "Week complete."

    return {
        "message": message,
        "analysis": None,
        "source": "rules",
    }


def _sync_data(user, today):
    """Sync Oura and Calendar data before analysis."""
    yesterday = today - timedelta(days=1)

    # Oura sync
    if user.oura_pat or user.oura_access_token:
        try:
            from app.services.data_sync import sync_daily
            from flask import current_app
            sync_daily(current_app._get_current_object(), target_date=yesterday)
        except Exception as e:
            logging.getLogger("ai").warning(f"Oura sync failed: {e}")

    # Calendar sync
    if user.google_access_token and user.google_calendar_ids:
        try:
            from app.services.google_calendar import GoogleCalendarClient
            from flask import current_app
            client = GoogleCalendarClient(current_app.config, user_id=user.id)
            client.sync_events(today)
        except Exception as e:
            logging.getLogger("ai").warning(f"Calendar sync failed: {e}")


def _store_result(user, today, result, is_weekly=False):
    """Store the AI insight in the database."""
    insight_type = "weekly" if is_weekly else "morning"

    # Upsert: update if exists, insert if not
    existing = AIInsight.query.filter_by(
        user_id=user.id,
        date=today,
        insight_type=insight_type,
    ).first()

    analysis_data = result.get("insight") or result.get("analysis")

    if existing:
        existing.message = result["message"]
        existing.analysis_json = json.dumps(analysis_data) if analysis_data else None
        existing.source = result.get("source", "ai")
    else:
        insight = AIInsight(
            user_id=user.id,
            date=today,
            insight_type=insight_type,
            message=result["message"],
            analysis_json=json.dumps(analysis_data) if analysis_data else None,
            source=result.get("source", "ai"),
        )
        db.session.add(insight)

    db.session.commit()


def _send_push(app, user, result, logger):
    """Send push notification with the insight."""
    try:
        from app.models import PushSubscription
        from pywebpush import webpush, WebPushException

        subscriptions = PushSubscription.query.filter_by(user_id=user.id).all()
        if not subscriptions:
            logger.info("No push subscriptions — skipping notification")
            return

        vapid_private = app.config.get("VAPID_PRIVATE_KEY")
        vapid_email = app.config.get("VAPID_CLAIM_EMAIL")

        if not vapid_private:
            logger.warning("No VAPID key configured — skipping push")
            return

        payload = json.dumps({
            "title": "Grow",
            "body": result["message"][:200],
            "url": "/",
        })

        sent = 0
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=payload,
                    vapid_private_key=vapid_private,
                    vapid_claims={"sub": vapid_email},
                )
                sent += 1
            except WebPushException as e:
                if "410" in str(e) or "404" in str(e):
                    # Subscription expired — clean up
                    db.session.delete(sub)
                    logger.info(f"Removed expired subscription {sub.id}")
                else:
                    logger.warning(f"Push failed for sub {sub.id}: {e}")

        db.session.commit()
        logger.info(f"Sent push to {sent}/{len(subscriptions)} devices")

    except ImportError:
        logger.warning("pywebpush not installed — skipping push")
    except Exception as e:
        logger.error(f"Push notification error: {e}")


if __name__ == "__main__":
    sys.exit(main())
