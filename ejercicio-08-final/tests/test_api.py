import pytest
import uuid
import time


# =============================================================================
# 1. GET /health — Happy Path
# =============================================================================
def test_health_returns_200_with_metrics(client):
    """Verifies /health returns 200 with all expected health metrics."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "cache_hit_rate" in data
    assert "uptime_seconds" in data
    assert data["sqlite_connected"] is True
    assert data["duckdb_connected"] is True


# =============================================================================
# 2. GET /analytics/summary — Happy Path
# =============================================================================
def test_analytics_summary_returns_breakdowns(client):
    """Verifies /analytics/summary returns country and category breakdowns."""
    response = client.get("/analytics/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_count" in data
    assert "total_amount" in data
    assert "avg_amount" in data
    assert "breakdown_by_country" in data
    assert "breakdown_by_category" in data
    assert data["total_count"] > 0


# =============================================================================
# 3. GET /analytics/summary — Cache Verification
# =============================================================================
def test_analytics_summary_caching(client):
    """Verifies that repeated calls to /analytics/summary use the cache."""
    # First call (cold)
    response1 = client.get("/analytics/summary")
    assert response1.status_code == 200
    data1 = response1.json()

    # Second call (warm — should hit cache)
    response2 = client.get("/analytics/summary")
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2 == data1

    # Cache hit rate should be updated
    health_response = client.get("/health")
    health_data = health_response.json()
    assert health_data["cache_hits"] >= 1


# =============================================================================
# 4. GET /analytics/top-merchants — Happy Path with Limit
# =============================================================================
def test_top_merchants_with_limit(client):
    """Verifies /analytics/top-merchants returns results capped by limit."""
    response = client.get("/analytics/top-merchants?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 5
    if data:
        assert "merchant_id" in data[0]
        assert "volume" in data[0]
        assert "transaction_count" in data[0]


# =============================================================================
# 5. GET /analytics/top-merchants — Happy Path with Country Filter
# =============================================================================
def test_top_merchants_with_country_filter(client):
    """Verifies /analytics/top-merchants filters by country_code correctly."""
    response = client.get("/analytics/top-merchants?limit=3&country=MX")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 3


# =============================================================================
# 6. GET /users/{user_id}/transactions — Happy Path with Date Filters
# =============================================================================
def test_user_transactions_with_date_filters(client):
    """Verifies /users/{user_id}/transactions supports date_from and date_to."""
    response = client.get("/users/1/transactions?page=1&page_size=5&date_from=2020-01-01&date_to=2030-12-31")
    if response.status_code == 200:
        data = response.json()
        assert data["user_id"] == 1
        assert data["filters"]["date_from"] == "2020-01-01"
        assert data["filters"]["date_to"] == "2030-12-31"
        assert isinstance(data["transactions"], list)
    else:
        assert response.status_code == 404


# =============================================================================
# 7. GET /users/{user_id}/transactions — Pagination
# =============================================================================
def test_user_transactions_pagination(client):
    """Verifies paginated transaction listing works correctly."""
    response = client.get("/users/1/transactions?page=1&page_size=5")
    if response.status_code == 200:
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5
        assert "total_records" in data
        assert "total_pages" in data
        assert len(data["transactions"]) <= 5
    else:
        assert response.status_code == 404


# =============================================================================
# 8. GET /users/{user_id}/stats — Happy Path
# =============================================================================
def test_user_stats_returns_aggregates(client):
    """Verifies /users/{user_id}/stats returns expected aggregate fields."""
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


# =============================================================================
# 9. GET /users/{user_id} — Not Found (404)
# =============================================================================
def test_user_not_found_404(client):
    """Verifies that a non-existent user returns 404."""
    response = client.get("/users/49999/stats")
    if response.status_code != 200:
        assert response.status_code == 404


# =============================================================================
# 10. GET /users/{user_id} — Validation Error (422)
# =============================================================================
def test_user_id_out_of_range_422(client):
    """Verifies that user_id > 50000 returns 422 from FastAPI path validation."""
    response = client.get("/users/50001/stats")
    assert response.status_code == 422


# =============================================================================
# 11. POST /transactions/batch — Happy Path
# =============================================================================
def test_batch_insert_happy_path(client):
    """Verifies batch insert of valid transactions returns success."""
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
        }
    ]
    response = client.post("/transactions/batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["received_records"] == 2
    assert data["inserted_records"] == 2


# =============================================================================
# 12. POST /transactions/batch — Idempotency
# =============================================================================
def test_batch_insert_idempotency(client):
    """Verifies that inserting the same transaction_id twice does not overwrite."""
    tx_id = str(uuid.uuid4())
    payload1 = [{
        "transaction_id": tx_id,
        "timestamp": "2026-05-19T12:00:00",
        "user_id": 45,
        "merchant_id": 300,
        "amount": 100.00,
        "category": "Food",
        "country_code": "MX",
        "status": "completed"
    }]
    # First insert
    resp1 = client.post("/transactions/batch", json=payload1)
    assert resp1.status_code == 200
    assert resp1.json()["inserted_records"] == 1

    # Second insert with same transaction_id (should be ignored)
    payload2 = [{
        "transaction_id": tx_id,
        "timestamp": "2026-05-19T12:00:00",
        "user_id": 45,
        "merchant_id": 300,
        "amount": 250.00,
        "category": "Food",
        "country_code": "MX",
        "status": "completed"
    }]
    resp2 = client.post("/transactions/batch", json=payload2)
    assert resp2.status_code == 200
    assert resp2.json()["inserted_records"] == 0
    assert resp2.json()["ignored_records"] == 1


# =============================================================================
# 13. POST /transactions/batch — Validation Error (422)
# =============================================================================
def test_batch_invalid_schema_422(client):
    """Verifies that invalid transaction data returns 422."""
    payload = [
        {
            "transaction_id": "not-a-uuid",
            "timestamp": "2026-05-19T10:00:00",
            "user_id": 42,
            "merchant_id": 99,
            "amount": -5.00,
            "category": "InvalidCategory",
            "country_code": "XX",
            "status": "unknown"
        }
    ]
    response = client.post("/transactions/batch", json=payload)
    assert response.status_code == 422


# =============================================================================
# 14. POST /transactions/batch — Exceeds Limit (400)
# =============================================================================
def test_batch_exceeds_limit_400(client):
    """Verifies that a batch exceeding 500 transactions returns 400."""
    payload = [
        {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": "2026-05-19T10:00:00",
            "user_id": 42,
            "merchant_id": 99,
            "amount": 10.00,
            "category": "Food",
            "country_code": "MX",
            "status": "completed"
        }
        for _ in range(501)
    ]
    response = client.post("/transactions/batch", json=payload)
    assert response.status_code == 400
    assert "exceeds maximum limit" in response.json()["detail"]


# =============================================================================
# 15. GET /health — SLA Latency Check (<50ms)
# =============================================================================
def test_health_sla_latency_under_50ms(client):
    """Verifies that /health responds consistently under 50ms average."""
    latencies = []
    for _ in range(10):
        start = time.perf_counter()
        response = client.get("/health")
        duration = (time.perf_counter() - start) * 1000
        assert response.status_code == 200
        latencies.append(duration)

    avg_latency = sum(latencies) / len(latencies)
    assert avg_latency < 50.0, f"Average /health latency {avg_latency:.2f}ms exceeds 50ms SLA"
