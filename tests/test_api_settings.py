import pytest
import json

def test_get_settings(client):
    """Test GET /api/settings endpoint."""
    rv = client.get('/api/settings')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'DETECTOR_MODEL' in data
    assert data['DETECTOR_MODEL'] == 'dlib'

def test_update_settings_valid(client):
    """Test POST /api/settings with valid data."""
    rv = client.post('/api/settings', json={
        'DETECTOR_MODEL': 'mediapipe',
        'TOLERANCE': 0.45
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['success'] is True
    
    # Verify persistence
    rv = client.get('/api/settings')
    data = rv.get_json()
    assert data['DETECTOR_MODEL'] == 'mediapipe'
    assert float(data['TOLERANCE']) == 0.45

def test_update_settings_invalid(client):
    """Test POST /api/settings with invalid values."""
    # Invalid Detector
    rv = client.post('/api/settings', json={'DETECTOR_MODEL': 'invalid_model'})
    assert rv.status_code == 200 # API returns 200 but with errors list
    data = rv.get_json()
    assert len(data['errors']) > 0
    assert "must be 'dlib' or 'mediapipe'" in data['errors'][0]

    # Invalid Number
    rv = client.post('/api/settings', json={'TOLERANCE': 'not_a_number'})
    data = rv.get_json()
    assert len(data['errors']) > 0
