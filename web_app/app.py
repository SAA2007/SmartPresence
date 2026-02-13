import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify
from web_app.config import Config
from web_app.routes.api import api_bp
from web_app.routes.views import views_bp
from web_app.video_stream import video_stream
from ai_module import common


def create_app():
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))

    app.config.from_object(Config)
    app.config['PROJECT_ROOT'] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'smartpresence-secret-change-me')

    # Session cookie security
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = 28800  # 8 hours

    # ── Upload / Request Size Limit ──
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB (base64 image ≈ 1.33× raw)

    # ── CSRF Protection ──
    try:
        from flask_wtf.csrf import CSRFProtect, CSRFError
        csrf = CSRFProtect(app)
        # csrf = None

        # Exempt public endpoints (no CSRF token available before authentication)
        # All other state-changing endpoints are protected via X-CSRFToken header
        # (injected by safeFetch in base.html)
        from web_app.routes.api import auth_login, student_lookup
        csrf.exempt(auth_login)
        csrf.exempt(student_lookup)

        @app.errorhandler(CSRFError)
        def handle_csrf_error(e):
            return jsonify({"error": "CSRF token missing or invalid"}), 400
    except ImportError:
        pass  # Flask-WTF not installed

    # ── Rate Limiting ──
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        limiter = Limiter(
            get_remote_address,
            app=app,
            default_limits=[],  # No global limit
            storage_uri="memory://",
        )
        # Store limiter on app so api.py can access it
        app.limiter = limiter
    except ImportError:
        app.limiter = None  # Flask-Limiter not installed yet

    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)

    # Ensure crash reports directory exists
    os.makedirs(common.CRASH_REPORTS_DIR, exist_ok=True)

    return app


if __name__ == '__main__':
    app = create_app()
    log = common.get_logger('server')

    # ── Default Credentials Warning ──
    _defaults = {
        'ADMIN_PASSWORD': 'admin123',
        'SETTINGS_PIN': '1234',
        'SECRET_KEY': 'smartpresence-secret-change-me',
        'DB_ENCRYPTION_KEY': 'smartpresence-encryption-key-change-me',
    }
    insecure = [k for k, v in _defaults.items() if os.environ.get(k, v) == v]
    if insecure:
        log.warning("=" * 60)
        log.warning("INSECURE DEFAULTS DETECTED — change before production!")
        for key in insecure:
            log.warning("  ⚠  %s is still set to its default value", key)
        log.warning("Edit .env to set secure values.")
        log.warning("=" * 60)

    log.info("Starting AI Video Stream...")
    video_stream.start()

    log.info("Starting Flask Server on http://localhost:5000")
    log.info("Open your browser to http://localhost:5000")

    try:
        app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
    finally:
        video_stream.stop()
        log.info("Server Stopped.")
