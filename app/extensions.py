"""Shared Flask extension instances (initialised in create_app)."""

from flask_wtf import CSRFProtect

csrf = CSRFProtect()