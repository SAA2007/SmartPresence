import pytest
import sqlite3
import os
import sys

# Add project root to path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_app.app import create_app
from ai_module.settings import SettingsManager
from ai_module import common

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # Use a temporary DB file
    db_fd, db_path = "test_db.sqlite", "test_db.sqlite"
    
    # Override common.DB_PATH for AI modules
    original_db_path = common.DB_PATH
    common.DB_PATH = os.path.abspath(db_path)
    
    app = create_app()
    app.config.update({
        "TESTING": True,
        "DATABASE": common.DB_PATH,
        "WTF_CSRF_ENABLED": False,  # Disable CSRF for easier API testing
    })

    # Initialize DB schema
    with app.app_context():
        from web_app.database.init_db import init_db
        init_db()

    yield app

    # Cleanup
    common.DB_PATH = original_db_path
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except:
            pass

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test runner for the app's CLI commands."""
    return app.test_cli_runner()

@pytest.fixture(autouse=True)
def clean_settings():
    """Reset SettingsManager cache before each test."""
    SettingsManager._cache = {}
