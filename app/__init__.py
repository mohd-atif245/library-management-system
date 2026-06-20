"""
Library Management System
--------------------------
A Flask web application for managing library book loans, fines,
and user accounts across student and librarian roles.
"""

import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()


def create_app(test_config=None):
    """
    Application factory.

    Creates and configures the Flask app instance. Accepts an optional
    test_config dict to override settings during automated testing.
    """
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", os.urandom(32)),
        DATABASE=os.environ.get("DATABASE", "library.db"),
        FINE_RATE_PER_DAY=float(os.environ.get("FINE_RATE_PER_DAY", 10)),
        LOAN_PERIOD_DAYS=int(os.environ.get("LOAN_PERIOD_DAYS", 14)),
        MAX_LOANS_PER_STUDENT=int(os.environ.get("MAX_LOANS_PER_STUDENT", 3)),
        WTF_CSRF_ENABLED=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )

    if test_config:
        app.config.update(test_config)

    # ------------------------------------------------------------------
    # Extensions
    # ------------------------------------------------------------------
    from app.extensions import csrf
    csrf.init_app(app)

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    from app import db
    db.init_app(app)

    # ------------------------------------------------------------------
    # Blueprints
    # ------------------------------------------------------------------
    from app.routes.auth import auth_bp
    from app.routes.student import student_bp
    from app.routes.librarian import librarian_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(librarian_bp)

    return app