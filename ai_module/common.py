import os
import logging

# ── Paths ──
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENCODINGS_PATH = os.path.join(PROJECT_ROOT, "ai_module", "encodings.pickle")
DB_PATH = os.path.join(PROJECT_ROOT, "web_app", "database", "attendance.db")
CRASH_REPORTS_DIR = os.path.join(PROJECT_ROOT, "crash_reports")
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

# ── Load .env ──
def _load_env():
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    os.environ.setdefault(key.strip(), value.strip())

_load_env()

# ── Camera ──
CAMERA_ID = 0
FRAME_WIDTH = 1920
FRAME_HEIGHT = 1080

# ── Colors (BGR) ──
COLOR_GREEN = (0, 255, 0)
COLOR_RED = (0, 0, 255)
COLOR_BLUE = (255, 0, 0)
COLOR_YELLOW = (0, 255, 255)
COLOR_ORANGE = (0, 165, 255)

# ── Recognition ──
TOLERANCE = 0.5
DETECTION_SCALE = 0.5
FRAME_SKIP = 30  # Legacy

# ── Scheduling & Tagging ──
LATE_THRESHOLD = 10       # Minutes after class start → "Late"
DISAPPEAR_THRESHOLD = 15  # Minutes unseen → "Disappeared"
RECHECK_INTERVAL = 300    # Seconds between disappearance scans (5 min)
SYSTEM_MODE = 'auto'      # 'auto' | 'force_on' | 'force_off'

# ── Auth ──
SETTINGS_PIN = os.environ.get('SETTINGS_PIN', '1234')

# ── Telegram ──
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

# ── Logging ──
LOG_LEVEL = logging.INFO

# Valid attendance statuses
VALID_STATUSES = ['On Time', 'Present', 'Late', 'Absent', 'Disappeared',
                  'Early Leave', 'Permitted', 'Excused']

# ── Setup Logger ──
def get_logger(name='smartpresence'):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '[%(levelname)s] %(message)s'
        ))
        logger.addHandler(handler)
    logger.setLevel(LOG_LEVEL)
    return logger

log = get_logger()
