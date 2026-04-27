#!/usr/bin/env python3
"""Daily Oura sync — run via cron at 7:00 AM.

Usage:
    python scripts/sync_oura.py              # Sync yesterday
    python scripts/sync_oura.py --backfill 30  # Backfill last 30 days

Crontab entry:
    0 7 * * * cd /home/pi/grow && venv/bin/python scripts/sync_oura.py >> logs/sync.log 2>&1
"""

import sys
import argparse
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.services.data_sync import sync_daily, backfill


def main():
    parser = argparse.ArgumentParser(description="Sync Oura data")
    parser.add_argument("--backfill", type=int, help="Backfill N days of history")
    parser.add_argument("--date", type=str, help="Sync a specific date (YYYY-MM-DD)")
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("sync")

    app = create_app()

    if args.backfill:
        logger.info(f"Backfilling {args.backfill} days...")
        results = backfill(app, days=args.backfill)
        success = sum(1 for r in results if r.get("success"))
        logger.info(f"Backfill complete: {success}/{len(results)} days synced")
        return 0

    if args.date:
        from datetime import date
        target = date.fromisoformat(args.date)
    else:
        target = None  # defaults to yesterday

    result = sync_daily(app, target_date=target)

    if result.get("success"):
        logger.info(f"Sync complete: {result}")
        return 0
    else:
        logger.error(f"Sync failed: {result.get('error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
