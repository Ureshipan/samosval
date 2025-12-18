import os
import sqlite3
from datetime import datetime

from flask import current_app, g
from werkzeug.security import generate_password_hash


def get_db() -> sqlite3.Connection:
    """Return a SQLite connection stored in Flask's `g`."""
    if "db" not in g:
        db_path = current_app.config["DATABASE"]
        g.db = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None) -> None:  # pragma: no cover - simple resource cleanup
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    """Initialize database schema from schema.sql."""
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        sql = f.read().decode("utf-8")
        db.executescript(sql)
    db.commit()


def ensure_root_user() -> None:
    """Create default root:root admin user if missing."""
    db = get_db()
    cur = db.execute("SELECT id FROM users WHERE username = ?", ("root",))
    row = cur.fetchone()
    if row is None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        password_hash = generate_password_hash("root")
        db.execute(
            """
            INSERT INTO users (username, password_hash, role, is_active, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("root", password_hash, "admin", 1, now),
        )
        db.commit()


def init_db_if_needed() -> None:
    """Create DB file and schema if needed, and ensure root user exists."""
    db_path = current_app.config["DATABASE"]
    first_time = not os.path.exists(db_path)
    if first_time:
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        init_db()
    # Always ensure root user
    ensure_root_user()


def init_app(app) -> None:
    """Register DB teardown with Flask app."""
    app.teardown_appcontext(close_db)


def write_audit(user_id, action: str, target_id: int | None, details: str | None) -> None:
    """Append record to audit_log table."""
    db = get_db()
    now = datetime.utcnow().isoformat(timespec="seconds")
    db.execute(
        """
        INSERT INTO audit_log (user_id, action, target_id, details, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, action, target_id, details, now),
    )
    db.commit()



