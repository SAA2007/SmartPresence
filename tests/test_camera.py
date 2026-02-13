import pytest
import sqlite3
from ai_module.camera_manager import CameraManager
from ai_module import common

def test_get_active_camera_defaults(app):
    """Test fallback when no cameras in DB."""
    # Ensure DB is empty of cameras
    with sqlite3.connect(common.DB_PATH) as conn:
        conn.execute("DELETE FROM cameras")
        conn.commit()
    
    cam = CameraManager.get_active_camera()
    assert cam['source'] == '0'
    # Name might be 'Default Camera' or similar fallback
    assert 'Default' in cam['name']

def test_get_active_camera_priority(app):
    """Test that we get the first active camera by ID."""
    with sqlite3.connect(common.DB_PATH) as conn:
        conn.execute("DELETE FROM cameras")
        # Insert Cam 2 (Active)
        conn.execute("INSERT INTO cameras (id, name, source, is_active) VALUES (2, 'Cam B', '1', 1)")
        # Insert Cam 1 (Inactive)
        conn.execute("INSERT INTO cameras (id, name, source, is_active) VALUES (1, 'Cam A', '0', 0)")
        # Insert Cam 3 (Active, but ID is higher than 2)
        conn.execute("INSERT INTO cameras (id, name, source, is_active) VALUES (3, 'Cam C', '2', 1)")
        conn.commit()

    cam = CameraManager.get_active_camera()
    # Should skip Cam 1 (inactive)
    # Should pick Cam 2 (lowest ID among active)
    assert cam['name'] == 'Cam B'
    assert cam['source'] == '1'

def test_get_all_cameras(app):
    """Test listing all cameras."""
    with sqlite3.connect(common.DB_PATH) as conn:
        conn.execute("DELETE FROM cameras")
        conn.execute("INSERT INTO cameras (name, source) VALUES ('Test1', '0')")
        conn.execute("INSERT INTO cameras (name, source) VALUES ('Test2', '1')")
        conn.commit()

    cams = CameraManager.get_all_cameras()
    assert len(cams) == 2
    assert cams[0]['name'] == 'Test1'
    assert cams[1]['name'] == 'Test2'
