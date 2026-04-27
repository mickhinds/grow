"""Lightweight schema migration — adds missing columns without losing data.

This avoids the need to delete the database every time we add a field.
On each startup, it compares the SQLAlchemy models to the actual tables
and issues ALTER TABLE for any missing columns.
"""

import logging
from sqlalchemy import inspect, text

from app.models import db

logger = logging.getLogger(__name__)

# Map Python/SQLAlchemy types to SQLite column types
TYPE_MAP = {
    "INTEGER": "INTEGER",
    "VARCHAR": "TEXT",
    "TEXT": "TEXT",
    "FLOAT": "REAL",
    "BOOLEAN": "INTEGER",
    "DATE": "DATE",
    "DATETIME": "DATETIME",
}


def _sqlite_type(sa_column) -> str:
    """Convert a SQLAlchemy column type to a SQLite type string."""
    type_name = sa_column.type.__class__.__name__.upper()
    for key, val in TYPE_MAP.items():
        if key in type_name:
            return val
    return "TEXT"


def auto_migrate(app):
    """Add any missing columns to existing tables. Safe and non-destructive."""
    with app.app_context():
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        for table_name, table in db.metadata.tables.items():
            if table_name not in existing_tables:
                # Table doesn't exist yet — create_all() will handle it
                continue

            existing_cols = {col["name"] for col in inspector.get_columns(table_name)}

            for column in table.columns:
                if column.name not in existing_cols:
                    col_type = _sqlite_type(column)
                    default = ""
                    if column.default is not None:
                        val = column.default.arg
                        if isinstance(val, str):
                            default = f" DEFAULT '{val}'"
                        elif isinstance(val, (int, float)):
                            default = f" DEFAULT {val}"
                        elif isinstance(val, bool):
                            default = f" DEFAULT {int(val)}"

                    sql = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}{default}"
                    logger.info(f"Migration: {sql}")
                    db.session.execute(text(sql))

        db.session.commit()
        logger.info("Migration check complete")
