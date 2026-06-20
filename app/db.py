"""
Database helpers
-----------------
Provides a per-request SQLite connection (stored on Flask's `g` object),
schema initialisation, and seed data for first-run.

Design decisions
----------------
* One connection per request, closed in teardown — avoids both the
  "new connection per query" anti-pattern and global connection sharing.
* Parameterised queries everywhere — no string formatting near SQL.
* Schema defined once here; routes never issue DDL.
"""

import sqlite3
import uuid
from datetime import datetime

import click
from flask import current_app, g


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

def get_db():
    """
    Return the request-scoped database connection.

    Opens a new connection if one does not already exist for this request.
    Uses sqlite3.Row as row_factory so columns are accessible by name.
    """
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        # Enforce FK constraints (SQLite disables them by default)
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    """Close the request-scoped connection (registered as teardown handler)."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    """Register lifecycle hooks on the app instance."""
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db():
    """Create tables (idempotent) and populate seed data if empty."""
    db = get_db()

    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id   TEXT PRIMARY KEY,
            name      TEXT NOT NULL,
            role      TEXT NOT NULL CHECK(role IN ('Student', 'Librarian')),
            password  TEXT NOT NULL,
            dept      TEXT NOT NULL,
            semester  INTEGER,
            is_active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS books (
            book_id         TEXT PRIMARY KEY,
            title           TEXT NOT NULL,
            author          TEXT NOT NULL,
            dept            TEXT NOT NULL,
            isbn            TEXT,
            total_copies    INTEGER NOT NULL CHECK(total_copies >= 0),
            available_copies INTEGER NOT NULL CHECK(available_copies >= 0),
            borrow_count    INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS transactions (
            txn_id      TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL REFERENCES users(user_id),
            book_id     TEXT NOT NULL REFERENCES books(book_id),
            issue_date  TEXT NOT NULL,
            due_date    TEXT NOT NULL,
            return_date TEXT,
            status      TEXT NOT NULL CHECK(status IN ('Issued', 'Returned'))
        );

        CREATE TABLE IF NOT EXISTS fines (
            fine_id  TEXT PRIMARY KEY,
            txn_id   TEXT NOT NULL REFERENCES transactions(txn_id),
            user_id  TEXT NOT NULL REFERENCES users(user_id),
            amount   REAL NOT NULL CHECK(amount >= 0),
            is_paid  INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            log_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       TEXT,
            activity_type TEXT NOT NULL,
            timestamp     TEXT NOT NULL,
            status        TEXT NOT NULL,
            details       TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_txn_user   ON transactions(user_id);
        CREATE INDEX IF NOT EXISTS idx_txn_book   ON transactions(book_id);
        CREATE INDEX IF NOT EXISTS idx_txn_status ON transactions(status);
        CREATE INDEX IF NOT EXISTS idx_fines_user ON fines(user_id);
    """)

    _seed(db)
    db.commit()


def _seed(db):
    """Insert demo data only when the users table is empty."""
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        return

    from werkzeug.security import generate_password_hash

    stu_pw  = generate_password_hash("student123")
    lib_pw  = generate_password_hash("librarian123")

    db.executemany(
        "INSERT INTO users VALUES (?,?,?,?,?,?,?)",
        [
            ("STU001", "Ali Khan",     "Student",   stu_pw, "CS",  3, 1),
            ("STU002", "Sana Ahmed",   "Student",   stu_pw, "EE",  2, 1),
            ("STU003", "Zain Malik",   "Student",   stu_pw, "CS",  5, 1),
            ("STU004", "Hira Baig",    "Student",   stu_pw, "ME",  4, 1),
            ("LIB001", "Miss Sarwat",  "Librarian", lib_pw, "N/A", 0, 1),
        ],
    )

    db.executemany(
        "INSERT INTO books VALUES (?,?,?,?,?,?,?,?)",
        [
            ("B001", "Clean Code",                     "Robert C. Martin", "CS",  "9780132350884", 4, 4, 31),
            ("B002", "Database System Concepts",       "Silberschatz",     "CS",  "9780078022159", 3, 2, 19),
            ("B003", "Digital Logic Design",           "Morris Mano",      "EE",  "9780131989245", 4, 4,  9),
            ("B004", "Introduction to Algorithms",     "Cormen et al.",    "CS",  "9780262033848", 2, 2, 14),
            ("B005", "Engineering Mathematics",        "K.A. Stroud",      "ME",  "9781137031204", 5, 5, 22),
            ("B006", "Computer Networks",              "Tanenbaum",        "CS",  "9780132126953", 3, 3, 17),
            ("B007", "Signals and Systems",            "Oppenheim",        "EE",  "9780138147570", 2, 2,  6),
        ],
    )


@click.command("init-db")
def init_db_command():
    """CLI command: flask init-db — create tables and seed data."""
    init_db()
    click.echo("Database initialised.")


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

def log_activity(user_id: str, activity_type: str, status: str, details: str):
    """
    Append one row to activity_log.

    Uses its own connection call so it can be invoked from anywhere;
    the connection is still the same per-request g.db instance.
    """
    db = get_db()
    db.execute(
        """INSERT INTO activity_log (user_id, activity_type, timestamp, status, details)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, activity_type, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status, details),
    )
    db.commit()


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

def new_id(prefix: str) -> str:
    """Generate a collision-free prefixed ID using UUID4."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"