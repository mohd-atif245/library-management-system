"""
Authentication routes
----------------------
Handles login (GET/POST) and logout. Role-based redirect after login.
Includes basic brute-force mitigation via Flask-Limiter-style tracking
(no external dependency — uses the session for a lightweight attempt counter).
"""

from flask import (
    Blueprint, flash, redirect, render_template,
    request, session, url_for, current_app,
)
from werkzeug.security import check_password_hash

from app.db import get_db, log_activity

auth_bp = Blueprint("auth", __name__)

_MAX_ATTEMPTS    = 5   # lock out after N consecutive failures
_LOCKOUT_MINUTES = 15  # minutes before the counter resets


@auth_bp.route("/", methods=["GET", "POST"])
def login():
    """
    Login page.

    GET  — render the login form.
    POST — validate credentials; redirect to the appropriate dashboard on
           success; flash an error and re-render on failure.

    Brute-force mitigation
    ----------------------
    Failed attempts are counted in the session. After _MAX_ATTEMPTS
    consecutive failures the form is locked for _LOCKOUT_MINUTES minutes.
    The counter resets on a successful login.
    """
    # Redirect already-authenticated users straight to their dashboard
    if "user_id" in session:
        return _redirect_by_role(session.get("role"))

    if request.method == "POST":
        user_id  = request.form.get("user_id", "").strip().upper()
        password = request.form.get("password", "")

        # ---- lightweight lockout check ----
        from datetime import datetime, timedelta
        attempts   = session.get("login_attempts", 0)
        locked_until = session.get("locked_until")
        if locked_until:
            locked_until_dt = datetime.fromisoformat(locked_until)
            if datetime.now() < locked_until_dt:
                remaining = int((locked_until_dt - datetime.now()).total_seconds() / 60) + 1
                flash(f"Too many failed attempts. Please wait {remaining} minute(s).", "danger")
                return render_template("login.html")
            else:
                session.pop("locked_until", None)
                session["login_attempts"] = 0

        # ---- validate inputs ----
        if not user_id or not password:
            flash("Please enter both your library ID and password.", "danger")
            return render_template("login.html")

        # ---- lookup user ----
        db   = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()

        if user and check_password_hash(user["password"], password):
            # Success — reset lockout counter, populate session
            session.clear()
            session["user_id"]  = user["user_id"]
            session["name"]     = user["name"]
            session["role"]     = user["role"]
            session["dept"]     = user["dept"]
            session["semester"] = user["semester"]
            session.permanent   = True

            log_activity(user_id, "LOGIN", "SUCCESS", f"Login from IP {request.remote_addr}")
            flash(f"Welcome back, {user['name']}!", "success")
            return _redirect_by_role(user["role"])

        else:
            # Failure — increment counter
            attempts += 1
            session["login_attempts"] = attempts
            if attempts >= _MAX_ATTEMPTS:
                lockout_until = datetime.now() + timedelta(minutes=_LOCKOUT_MINUTES)
                session["locked_until"] = lockout_until.isoformat()
                log_activity(user_id, "LOGIN_LOCKED", "FAILED",
                             f"Account locked after {attempts} failed attempts.")
                flash(f"Too many failed attempts. Please wait {_LOCKOUT_MINUTES} minutes.", "danger")
            else:
                log_activity(user_id, "LOGIN", "FAILED",
                             f"Invalid credentials. Attempt {attempts}/{_MAX_ATTEMPTS}.")
                flash("Invalid library ID or password.", "danger")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """Clear the session and redirect to the login page."""
    user_id = session.get("user_id", "unknown")
    log_activity(user_id, "LOGOUT", "SUCCESS", "Session terminated.")
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _redirect_by_role(role: str):
    if role == "Librarian":
        return redirect(url_for("librarian.dashboard"))
    return redirect(url_for("student.dashboard"))