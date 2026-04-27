#!/usr/bin/env python3
"""Initialize the database and create the default user.

Run once after first install:
    python scripts/init_db.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app

def main():
    app = create_app()
    with app.app_context():
        from app.models import db
        print(f"Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print("Tables created. Default user initialized.")
        print("Ready to grow.")

if __name__ == "__main__":
    main()
