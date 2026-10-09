"""Small SQLite helpers: open connections, create tables, make timestamps."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app, g


def now_iso():
    """Current UTC time as text, e.g. 2026-10-08T12:30:45.123456Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def connect(db_path):
    """Open a connection with foreign keys ON (SQLite needs this every time)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """One connection per request, closed automatically afterwards."""
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE_PATH"])
    return g.db


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    """Create the database file and any missing tables."""
    path = Path(app.config["DATABASE_PATH"])
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = Path(app.config["SCHEMA_PATH"]).read_text(encoding="utf-8")
    conn = connect(path)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()
