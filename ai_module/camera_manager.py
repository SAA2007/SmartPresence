import sqlite3
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_module import common

class CameraManager:
    """
    Manages camera configurations from the database.
    Replaces hardcoded CAMERA_ID.
    """
    
    @staticmethod
    def get_active_camera():
        """
        Get the primary active camera configuration.
        Returns dict with 'source', 'type', 'name' or None.
        """
        try:
            with sqlite3.connect(common.DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                # Get the first active camera, prioritizing by ID (creation order)
                row = conn.execute("""
                    SELECT * FROM cameras 
                    WHERE is_active = 1 
                    ORDER BY id ASC 
                    LIMIT 1
                """).fetchone()
                
                if row:
                    return dict(row)
        except Exception as e:
            common.get_logger('camera_manager').error(f"Failed to fetch camera config: {e}")
        
        # Fallback to defaults if DB fails or no camera found
        return {
            'source': str(common.CAMERA_ID),
            'type': 'usb',
            'name': 'Default Camera'
        }

    @staticmethod
    def get_all_cameras():
        """List all cameras for API."""
        try:
            with sqlite3.connect(common.DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT * FROM cameras ORDER BY id ASC").fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []
