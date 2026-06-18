import pytest
import uuid


# =============================================================================
# 1. GET /analytics/anomalies — Default Threshold
# =============================================================================
def test_anomalies_default_threshold(client):
    """Verifies /analytics/anomalies returns results using the default threshold."""
    response = client.get("/analytics/anomalies")
    assert response.status_code == 200
    data = response.json()
    assert "threshold" in data
    assert "period_days" in data
    assert data["period_days"] == 30
    assert "total_flagged_users" in data
    assert "anomalies" in data
    assert isinstance(data["anomalies"], list)


# =============================================================================
# 2. GET /analytics/anomalies — Custom Threshold
# =============================================================================
def test_anomalies_custom_threshold(client):
    """Verifies /analytics/anomalies respects a custom threshold parameter."""
    response = client.get("/analytics/anomalies?threshold=10")
    assert response.status_code == 200
    data = response.json()
    assert data["threshold"] == 10
    # All flagged users must have failed_count > threshold
    for anomaly in data["anomalies"]:
        assert anomaly["failed_count"] > 10


# =============================================================================
# 3. GET /analytics/anomalies — High Threshold (Empty Result)
# =============================================================================
def test_anomalies_high_threshold_empty(client):
    """Verifies that an extremely high threshold returns an empty list."""
    response = client.get("/analytics/anomalies?threshold=99999")
    assert response.status_code == 200
    data = response.json()
    assert data["total_flagged_users"] == 0
    assert data["anomalies"] == []


# =============================================================================
# 4. GET /analytics/anomalies — Response Structure
# =============================================================================
def test_anomalies_response_structure(client):
    """Verifies each anomaly item has the expected fields."""
    response = client.get("/analytics/anomalies?threshold=1")
    assert response.status_code == 200
    data = response.json()
    if data["anomalies"]:
        first = data["anomalies"][0]
        assert "user_id" in first
        assert "failed_count" in first
        assert isinstance(first["user_id"], int)
        assert isinstance(first["failed_count"], int)
        assert first["failed_count"] > 1


# =============================================================================
# 5. GET /analytics/anomalies — Threshold Validation (422)
# =============================================================================
def test_anomalies_invalid_threshold_422(client):
    """Verifies that threshold=0 returns 422 (ge=1 validation)."""
    response = client.get("/analytics/anomalies?threshold=0")
    assert response.status_code == 422
