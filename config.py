"""
YugKrit - Application Configuration
Loads settings from environment variables (see .env.example).
"""

import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _database_uri():
    configured_uri = os.environ.get("DATABASE_URL", "").strip()
    if not configured_uri:
        return f"sqlite:///{os.path.join(BASE_DIR, 'yugkrit.db')}"

    if configured_uri.startswith("sqlite:///"):
        sqlite_path = configured_uri[len("sqlite:///"):]
        if sqlite_path and sqlite_path != ":memory:" and not os.path.isabs(sqlite_path):
            sqlite_path = os.path.abspath(os.path.join(BASE_DIR, sqlite_path))
            return f"sqlite:///{sqlite_path.replace(os.sep, '/') }"

    return configured_uri


class Config:
    # --- Core Flask settings ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me-in-production")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # --- Database ---
    # SQLite for local dev. Structured so PostgreSQL can be swapped in later
    # by simply changing DATABASE_URL in the .env file.
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- File uploads ---
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "mp4", "docx", "xlsx"}

    # --- App metadata ---
    APP_NAME = "YugKrit"
    APP_TAGLINE = "CONNECTING INDIA'S CHALLENGES WITH INDIA'S POTENTIAL"

    # --- Security ---
    WTF_CSRF_ENABLED = True

    DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
