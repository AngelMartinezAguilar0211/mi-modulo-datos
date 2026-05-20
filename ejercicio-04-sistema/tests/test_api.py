import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient
import time

from app.main import app
from app.cache import cache

# Initialize client using with statement to trigger lifespan events
@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        # Clear cache before running tests to get predictable results
        cache.clear()
        yield c

# 1. GET /health Happy Path
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

# 4. GET /users/{user_id}/transactions Happy Path
def test_user_transactions_happy_path(client):
    # User 1 is highly likely to exist in the 1M dataset
    response = client.get("/users/1/transactions?page=1&page_size=5")
    if response.status_code == 200:
        data = response.json()
        assert data["user_id"] == 1
        assert data["page"] == 1
        assert data["page_size"] == 5
        assert "transactions" in data
        assert isinstance(data["transactions"], list)
        assert len(data["transactions"]) <= 5
    else:
        # If user 1 has no transactions in the dataset
        assert response.status_code == 404

# 5. GET /users/{user_id}/stats Happy Path
def test_user_stats_happy_path(client):
    response = client.get("/users/1/stats")
    if response.status_code == 200:
        data = response.json()
        assert data["user_id"] == 1
        assert "total_amount" in data
        assert "transaction_count" in data
        assert "most_frequent_category" in data
        assert "country_code" in data
    else:
        assert response.status_code == 404

# 6. GET /users/{user_id} Not Found Edge Cases (404 and 422)
def test_user_not_found_and_validation(client):
    # Non-existent user within valid range (should return 404)
    # Using 49999 which is very unlikely to have transactions unless generated
    response_404 = client.get("/users/49999/stats")
    if response_404.status_code != 200:
        assert response_404.status_code == 404
        
    # User ID out of range > 50000 (should return 422 due to FastAPI path parameter ge/le validation)
    response_422 = client.get("/users/50001/stats")
    assert response_422.status_code == 422

# 7. POST /transactions/batch Happy Path
def test_post_batch_happy_path(client):
    tx_id1 = str(uuid.uuid4())
    tx_id2 = str(uuid.uuid4())
    payload = [
        {
            "transaction_id": tx_id1,
            "timestamp": "2026-05-19T10:00:00",
            "user_id": 42,
            "merchant_id": 99,
            "amount": 150.75,
            "category": "Food",
            "country_code": "MX",
            "status": "completed"
        },
        {
            "transaction_id": tx_id2,
            "timestamp": "2026-05-19T10:05:00",
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
            "timestamp": "2026-05-19T10:05:00",
            "user_id": 42,
            "merchant_id": 100,
            "amount": 99.99,  # different amount, should overwrite
            "category": "Services",
            "country_code": "CO",
            "status": "completed"
        }
    ]
    response = client.post("/transactions/batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["received_records"] == 3
    assert data["inserted_records"] == 2  # 3 records received, 1 duplicate removed
    
    # Query the inserted user stats and transactions to verify insertion
    stats_resp = client.get("/users/42/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["transaction_count"] >= 2

# 8. POST /transactions/batch Validation Error (422)
def test_post_batch_invalid_schema(client):
    payload = [
        {
            "transaction_id": "not-a-uuid",  # invalid
            "timestamp": "2026-05-19T10:00:00",
            "user_id": 42,
            "merchant_id": 99,
            "amount": -5.00,  # invalid amount (must be >= 0.01)
            "category": "InvalidCategory",  # invalid category
            "country_code": "XX",  # invalid country
            "status": "unknown"  # invalid status
        }
    ]
    response = client.post("/transactions/batch", json=payload)
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert len(errors) > 0

# 9. POST /transactions/batch Too Large (400)
def test_post_batch_too_large(client):
    # Create 501 transactions
    payload = []
    for _ in range(501):
        payload.append({
            "transaction_id": str(uuid.uuid4()),
            "timestamp": "2026-05-19T10:00:00",
            "user_id": 42,
            "merchant_id": 99,
            "amount": 10.00,
            "category": "Food",
            "country_code": "MX",
            "status": "completed"
        })
    response = client.post("/transactions/batch", json=payload)
    assert response.status_code == 400
    assert "exceeds maximum limit" in response.json()["detail"]

# 10. GET /users/{user_id}/transactions Pagination Out of Range (400)
def test_pagination_out_of_range(client):
    # Query user 42 (for which transactions were just created) with an insane page number
    response = client.get("/users/42/transactions?page=9999&page_size=20")
    assert response.status_code == 400
    assert "out of range" in response.json()["detail"]

# 11. Health Latency SLA Check (< 50ms)
def test_health_sla_latency(client):
    # Warm up and run 10 times to get average latency
    latencies = []
    for _ in range(10):
        start = time.perf_counter()
        response = client.get("/health")
        duration = (time.perf_counter() - start) * 1000  # in ms
        assert response.status_code == 200
        latencies.append(duration)
        
    avg_latency = sum(latencies) / len(latencies)
    print(f"\nAverage /health latency: {avg_latency:.2f}ms")
    # Health endpoint MUST respond in less than 50ms always
    assert avg_latency < 50.0
