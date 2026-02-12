import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'smartpresence-dev-key-change-in-production')
    DB_PATH = os.path.join(PROJECT_ROOT, 'web_app', 'database', 'attendance.db')
    CAMERA_ID = 0
    FRAME_WIDTH = 1920
    FRAME_HEIGHT = 1080
