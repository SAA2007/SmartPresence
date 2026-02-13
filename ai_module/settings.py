import sqlite3
import logging
from ai_module import common

log = common.get_logger('settings')

class SettingsManager:
    """
    Manages persistent settings in the database.
    Falls back to defaults if DB is inaccessible or key is missing.
    """
    _cache = {}
    
    DEFAULTS = {
        'DETECTOR_MODEL': 'dlib',
        'TOLERANCE': '0.5',
        'DETECTION_SCALE': '0.5',
        'LATE_THRESHOLD': '10',
        'DISAPPEAR_THRESHOLD': '15',
        'RECHECK_INTERVAL': '300',
        'SYSTEM_MODE': 'auto',
        'FRAME_SKIP': '3'
    }

    @classmethod
    def get(cls, key, default=None, type_cast=str):
        """Get a setting with optional type casting and default override."""
        # Check cache first
        if key in cls._cache:
            val = cls._cache[key]
        else:
            val = cls._fetch_from_db(key)
            cls._cache[key] = val
        
        # Determine value (DB/Cache -> Provided Default -> Class Default)
        if val is None or val == '':
            if default is not None:
                final_val = default
            else:
                final_val = cls.DEFAULTS.get(key)
        else:
            final_val = val

        try:
            if type_cast == bool:
                return str(final_val).lower() in ('true', '1', 'yes', 'on')
            return type_cast(final_val)
        except Exception:
            # Fallback if casting fails
            if default is not None:
                return default
            return cls.DEFAULTS.get(key)

    @classmethod
    def set(cls, key, value):
        """Update a setting."""
        try:
            with sqlite3.connect(common.DB_PATH) as conn:
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                             (key, str(value)))
                conn.commit()
            cls._cache[key] = str(value) # Update cache
            return True
        except Exception as e:
            log.error(f"Failed to save setting {key}: {e}")
            return False

    @classmethod
    def get_all(cls):
        """Return all settings as dict."""
        try:
            with sqlite3.connect(common.DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT key, value FROM settings").fetchall()
                data = {row['key']: row['value'] for row in rows}
                # Merge with defaults ensuring all keys exist
                for k, v in cls.DEFAULTS.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception:
            return cls.DEFAULTS.copy()

    @classmethod
    def _fetch_from_db(cls, key):
        try:
            with sqlite3.connect(common.DB_PATH) as conn:
                row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
                if row:
                    return row[0]
        except Exception:
            pass
        return cls.DEFAULTS.get(key, '')
