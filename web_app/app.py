import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
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

    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)

    # Ensure crash reports directory exists
    os.makedirs(common.CRASH_REPORTS_DIR, exist_ok=True)

    return app


if __name__ == '__main__':
    app = create_app()
    log = common.get_logger('server')

    log.info("Starting AI Video Stream...")
    video_stream.start()

    log.info("Starting Flask Server on http://localhost:5000")
    log.info("Open your browser to http://localhost:5000")

    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    finally:
        video_stream.stop()
        log.info("Server Stopped.")
