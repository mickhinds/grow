#!/usr/bin/env python3
"""Send push notifications — run via cron.

Usage:
  # Morning nudge (9 AM) — only sends if no dashboard visit today
  python3 scripts/send_push.py --morning

  # Inactivity nudge — sends if no activity for 2+ days
  python3 scripts/send_push.py --inactivity

Cron examples (add to Pi with `crontab -e`):
  0 9 * * *  cd /home/mickfinn/grow && /home/mickfinn/grow/venv/bin/python3 scripts/send_push.py --morning
  0 20 * * * cd /home/mickfinn/grow && /home/mickfinn/grow/venv/bin/python3 scripts/send_push.py --inactivity
"""

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.models import db, User, PushSubscription, OuraDaily, IFSession, FoodLog, GardenHistory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def send_push_to_all(app, title, body, tag="grow-nudge", url="/"):
    """Send a push notification to all subscribed devices."""
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.error("pywebpush not installed. Run: pip install pywebpush")
        return False

    vapid_private = app.config.get("VAPID_PRIVATE_KEY", "")
    vapid_email = app.config.get("VAPID_CLAIM_EMAIL", "")

    if not vapid_private:
        logger.error("VAPID_PRIVATE_KEY not configured in .env")
        return False

    subscriptions = PushSubscription.query.all()
    if not subscriptions:
        logger.info("No push subscriptions found. Open the app in a browser first.")
        return False

    payload = json.dumps({
        "title": title,
        "body": body,
        "tag": tag,
        "url": url,
    })

    sent = 0
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth,
                    },
                },
                data=payload,
                vapid_private_key=vapid_private,
                vapid_claims={"sub": vapid_email},
            )
            sent += 1
            logger.info(f"Push sent to subscription {sub.id}")

        except WebPushException as e:
            status = getattr(e, 'response', None)
            status_code = status.status_code if status else None

            if status_code in (404, 410):
                # Subscription expired or unsubscribed — clean up
                logger.info(f"Removing expired subscription {sub.id}")
                db.session.delete(sub)
                db.session.commit()
            else:
                logger.error(f"Push failed for subscription {sub.id}: {e}")

        except Exception as e:
            logger.error(f"Push error for subscription {sub.id}: {e}")

    logger.info(f"Sent {sent}/{len(subscriptions)} push notifications.")
    return sent > 0


def check_morning_nudge(app):
    """Send a morning nudge if no activity has been logged today.

    Composes a message from the status sentence engine —
    same voice as the dashboard.
    """
    with app.app_context():
        user = db.session.get(User, 1)
        if not user:
            return

        today = date.today()

        # Check if user has already visited today (any IF log or food log today)
        has_if = IFSession.query.filter_by(user_id=1, date=today).first()
        has_food = FoodLog.query.filter_by(user_id=1, date=today).first()

        if has_if or has_food:
            logger.info("User already active today — skipping morning nudge.")
            return

        # Compose the nudge using the status sentence engine
        try:
            from app.services.status_sentence import compose_status_sentence
            sentence = compose_status_sentence(user, today)
        except Exception:
            sentence = "New day. Your garden is waiting."

        send_push_to_all(
            app,
            title="Grow",
            body=sentence,
            tag="grow-morning",
            url="/",
        )


def check_inactivity_nudge(app):
    """Send a gentle nudge if no activity for 2+ days.

    Not punitive — curious. "Haven't seen you in a bit."
    """
    with app.app_context():
        user = db.session.get(User, 1)
        if not user:
            return

        today = date.today()
        two_days_ago = today - timedelta(days=2)

        # Check for any recent activity
        recent_if = IFSession.query.filter(
            IFSession.user_id == 1,
            IFSession.date >= two_days_ago,
        ).first()
        recent_food = FoodLog.query.filter(
            FoodLog.user_id == 1,
            FoodLog.date >= two_days_ago,
        ).first()
        recent_garden = GardenHistory.query.filter(
            GardenHistory.user_id == 1,
            GardenHistory.date >= two_days_ago,
        ).first()

        if recent_if or recent_food or recent_garden:
            logger.info("Recent activity found — skipping inactivity nudge.")
            return

        # Find how many days since last activity
        last_history = GardenHistory.query.filter_by(
            user_id=1
        ).order_by(GardenHistory.date.desc()).first()

        if last_history:
            days_away = (today - last_history.date).days
            if days_away <= 1:
                return  # Just one day, not worth nudging

            body = f"It's been {days_away} days. Your garden misses you — even a small check-in counts."
        else:
            body = "Your garden is ready whenever you are. One small step today?"

        send_push_to_all(
            app,
            title="Grow",
            body=body,
            tag="grow-inactivity",
            url="/",
        )


def main():
    parser = argparse.ArgumentParser(description="Send Grow push notifications")
    parser.add_argument("--morning", action="store_true", help="Morning nudge (9 AM)")
    parser.add_argument("--inactivity", action="store_true", help="Inactivity nudge (2+ days)")
    parser.add_argument("--test", action="store_true", help="Send a test notification")
    args = parser.parse_args()

    app = create_app()

    if args.test:
        with app.app_context():
            send_push_to_all(
                app,
                title="Grow",
                body="Push notifications are working. Your garden is connected.",
                tag="grow-test",
            )
    elif args.morning:
        check_morning_nudge(app)
    elif args.inactivity:
        check_inactivity_nudge(app)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
