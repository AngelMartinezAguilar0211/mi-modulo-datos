import os
import sys
from pathlib import Path
import django

# Add exercise root directory to sys.path to allow imports when running pytest from root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Configure Django settings before importing any Django modules
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import pytest
import uuid
import time
from datetime import datetime, timezone
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from transactions.cache import cache
from transactions.models import Transaction


@pytest.fixture
def client():
    # Setup fresh caching
    cache.clear()
    return APIClient()


@pytest.fixture
def auth_client(db):
    client = APIClient()
    # Create test user and token for authentication tests
    user = User.objects.create_user(username="testuser", password="testpassword")
    token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    cache.clear()
    return client


# 1. GET /health Happy Path
@pytest.mark.django_db
def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "cache_hit_rate" in data
    assert "uptime_seconds" in data
    assert data["sqlite_connected"] is True
    assert data["duckdb_connected"] is True


# 2. GET /analytics/summary Happy Path & Caching verification
@pytest.mark.django_db
def test_analytics_summary_happy_path(client):
    # First call (cold)
    start_time = time.perf_counter()
    response1 = client.get("/analytics/summary")
    duration1 = time.perf_counter() - start_time

    assert response1.status_code == 200
    data1 = response1.json()
    assert "total_count" in data1
    assert "total_amount" in data1
    assert "avg_amount" in data1
    assert "breakdown_by_country" in data1
    assert "breakdown_by_category" in data1
    assert data1["total_count"] > 0

    # Second call (warm - should hit cache)
    start_time = time.perf_counter()
    response2 = client.get("/analytics/summary")
    duration2 = time.perf_counter() - start_time

    assert response2.status_code == 200
    data2 = response2.json()
    assert data2 == data1

    # Cache hit rate in health should be updated
    health_response = client.get("/health")
    health_data = health_response.json()
    assert health_data["cache_hits"] >= 1


# 3. GET /analytics/top-merchants Happy Path
@pytest.mark.django_db
def test_analytics_top_merchants_happy_path(client):
    # Test without country filter
    response = client.get("/analytics/top-merchants?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 5
    if data:
        assert "merchant_id" in data[0]
        assert "volume" in data[0]
        assert "transaction_count" in data[0]

    # Test with country filter
    response_mx = client.get("/analytics/top-merchants?limit=3&country=MX")
    assert response_mx.status_code == 200
    data_mx = response_mx.json()
    assert isinstance(data_mx, list)
    assert len(data_mx) <= 3


# 4. GET /users/{user_id}/transactions Unauthorized (401)
@pytest.mark.django_db
def test_user_transactions_unauthorized(client):
    response = client.get("/users/1/transactions")
    assert response.status_code == 401


# 5. GET /users/{user_id}/transactions Happy Path with Auth
@pytest.mark.django_db
def test_user_transactions_happy_path(auth_client):
    # Insert test transactions for user 1
    Transaction.objects.create(
        transaction_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        user_id=1,
        merchant_id=99,
        amount=150.0,
        category="Food",
        country_code="MX",
        status="completed"
    )

    response = auth_client.get("/users/1/transactions?page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == 1
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert "transactions" in data
    assert len(data["transactions"]) == 1
    assert data["transactions"][0]["category"] == "Food"


# 6. GET /users/{user_id}/stats Happy Path
@pytest.mark.django_db
def test_user_stats_happy_path(auth_client):
    # Insert mock user transactions to test aggregate calculation
    Transaction.objects.create(
        transaction_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        user_id=1,
        merchant_id=99,
        amount=150.0,
        category="Food",
        country_code="MX",
        status="completed"
    )
    Transaction.objects.create(
        transaction_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        user_id=1,
        merchant_id=100,
        amount=50.0,
        category="Food",
        country_code="CO",
        status="completed"
    )

    response = auth_client.get("/users/1/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == 1
    assert data["total_amount"] == 200.0
    assert data["transaction_count"] == 2
    assert data["most_frequent_category"] == "Food"
    assert data["country_code"] == "CO"  # CO and MX both have freq=1, alphabetical 'CO' comes first


# 7. GET /users/{user_id} Not Found Edge Cases (404 and 422)
@pytest.mark.django_db
def test_user_not_found_and_validation(auth_client):
    # User 999 exists in valid range but has no transactions (should return 404)
    response_404 = auth_client.get("/users/999/stats")
    assert response_404.status_code == 404

    # User ID out of range > 50000 (should return 422 due to view validation)
    response_422 = auth_client.get("/users/50001/stats")
    assert response_422.status_code == 422
    assert "detail" in response_422.json()


# 8. POST /transactions/batch Happy Path
@pytest.mark.django_db
def test_post_batch_happy_path(auth_client):
    tx_id1 = str(uuid.uuid4())
    tx_id2 = str(uuid.uuid4())
    payload = [
        {
            "transaction_id": tx_id1,
            "timestamp": "2026-05-19T10:00:00Z",
            "user_id": 42,
            "merchant_id": 99,
            "amount": 150.75,
            "category": "Food",
            "country_code": "MX",
            "status": "completed"
        },
        {
            "transaction_id": tx_id2,
            "timestamp": "2026-05-19T10:05:00Z",
            "user_id": 42,
            "merchant_id": 100,
            "amount": 25.50,
            "category": "Services",
            "country_code": "CO",
            "status": "completed"
        },
        # Duplicate within batch to test deduplication
        {
            "transaction_id": tx_id2,
            "timestamp": "2026-05-19T10:05:00Z",
            "user_id": 42,
            "merchant_id": 100,
            "amount": 99.99,  # different amount, should overwrite
            "category": "Services",
            "country_code": "CO",
            "status": "completed"
        }
    ]
    response = auth_client.post("/transactions/batch", payload, format="json")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["received_records"] == 3
    assert data["inserted_records"] == 2

    # Query the inserted user stats and transactions to verify insertion
    stats_resp = auth_client.get("/users/42/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["transaction_count"] == 2


# 9. POST /transactions/batch Validation Error (422)
@pytest.mark.django_db
def test_post_batch_invalid_schema(auth_client):
    payload = [
        {
            "transaction_id": "not-a-uuid",  # invalid
            "timestamp": "2026-05-19T10:00:00Z",
            "user_id": 42,
            "merchant_id": 99,
            "amount": -5.00,  # invalid amount (must be >= 0.01)
            "category": "InvalidCategory",  # invalid category
            "country_code": "XX",  # invalid country
            "status": "unknown"  # invalid status
        }
    ]
    response = auth_client.post("/transactions/batch", payload, format="json")
    assert response.status_code == 422
    assert "detail" in response.json()


# 10. GET /users/{user_id}/transactions Pagination Out of Range (400)
@pytest.mark.django_db
def test_pagination_out_of_range(auth_client):
    # Insert mock user transactions to allow checking page numbers
    Transaction.objects.create(
        transaction_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        user_id=42,
        merchant_id=99,
        amount=150.0,
        category="Food",
        country_code="MX",
        status="completed"
    )
    # Query with page number out of range
    response = auth_client.get("/users/42/transactions?page=9999&page_size=20")
    assert response.status_code == 400
    assert "out of range" in response.json()["detail"]


# 11. Health Latency SLA Check (< 50ms)
@pytest.mark.django_db
def test_health_sla_latency(client):
    latencies = []
    for _ in range(10):
        start = time.perf_counter()
        response = client.get("/health")
        duration = (time.perf_counter() - start) * 1000  # in ms
        assert response.status_code == 200
        latencies.append(duration)

    avg_latency = sum(latencies) / len(latencies)
    print(f"\nAverage /health latency: {avg_latency:.2f}ms")
    # Health endpoint MUST respond in less than 50ms on average
    assert avg_latency < 50.0
