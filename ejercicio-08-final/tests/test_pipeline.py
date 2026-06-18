import pytest
import uuid
import os
import csv
import io
import tempfile


# =============================================================================
# 1. CSV Extraction — Field Normalization
# =============================================================================
def test_csv_extraction_normalizes_fields(tmp_path):
    """Verifies that extract_from_csv normalizes timestamps, amounts, and country codes."""
    from pipeline.extract_csv import extract_from_csv

    csv_file = tmp_path / "test.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "transaction_id", "timestamp", "user_id", "merchant_id",
            "amount", "category", "country_code", "status"
        ])
        writer.writeheader()
        writer.writerow({
            "transaction_id": str(uuid.uuid4()),
            "timestamp": "2026-06-10T10:00:00Z",
            "user_id": "123",
            "merchant_id": "456",
            "amount": "99.9999",
            "category": "Food",
            "country_code": "mx",
            "status": "completed"
        })

    result = extract_from_csv(str(csv_file))
    assert len(result) == 1
    tx = result[0]
    # country_code should be uppercased
    assert tx["country_code"] == "MX"
    # amount should be rounded to 2 decimals
    assert tx["amount"] == 100.0
    # user_id and merchant_id should be integers
    assert isinstance(tx["user_id"], int)
    assert isinstance(tx["merchant_id"], int)


# =============================================================================
# 2. Transform — Rejects Invalid Amounts
# =============================================================================
def test_transform_rejects_invalid_amounts():
    """Verifies that amounts outside 0.01-5000.00 are rejected."""
    from pipeline.transform import transform_and_validate

    txs = [
        {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": "2026-06-10T10:00:00Z",
            "user_id": 1,
            "merchant_id": 100,
            "amount": -50.0,
            "category": "Food",
            "country_code": "MX",
            "status": "completed"
        },
        {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": "2026-06-10T10:00:00Z",
            "user_id": 1,
            "merchant_id": 100,
            "amount": 7500.0,
            "category": "Food",
            "country_code": "MX",
            "status": "completed"
        }
    ]

    valid, rejected, errors = transform_and_validate(txs, quarantine_dir=tempfile.mkdtemp())
    assert len(valid) == 0
    assert len(rejected) == 2
    assert errors["amount_out_of_range"] == 2


# =============================================================================
# 3. Transform — Rejects Invalid Categories
# =============================================================================
def test_transform_rejects_invalid_categories():
    """Verifies that categories not in the whitelist are rejected."""
    from pipeline.transform import transform_and_validate

    txs = [{
        "transaction_id": str(uuid.uuid4()),
        "timestamp": "2026-06-10T10:00:00Z",
        "user_id": 1,
        "merchant_id": 100,
        "amount": 50.0,
        "category": "Gambling",
        "country_code": "MX",
        "status": "completed"
    }]

    valid, rejected, errors = transform_and_validate(txs, quarantine_dir=tempfile.mkdtemp())
    assert len(valid) == 0
    assert len(rejected) == 1
    assert errors["invalid_category"] == 1


# =============================================================================
# 4. Transform — Quarantine File Written
# =============================================================================
def test_transform_quarantine_written():
    """Verifies that rejected transactions are written to quarantine JSONL file."""
    from pipeline.transform import transform_and_validate
    import json

    q_dir = tempfile.mkdtemp()

    txs = [{
        "transaction_id": "not-a-uuid",
        "timestamp": "2026-06-10T10:00:00Z",
        "user_id": 1,
        "merchant_id": 100,
        "amount": 50.0,
        "category": "Food",
        "country_code": "MX",
        "status": "completed"
    }]

    valid, rejected, errors = transform_and_validate(txs, quarantine_dir=q_dir)
    assert len(rejected) == 1

    # Verify quarantine file exists and contains the rejected entry
    files = os.listdir(q_dir)
    assert len(files) == 1
    assert files[0].endswith(".jsonl")

    with open(os.path.join(q_dir, files[0]), "r") as f:
        line = f.readline()
        entry = json.loads(line)
        assert "rejection_reasons" in entry
        assert "invalid_uuid" in entry["rejection_reasons"]


# =============================================================================
# 5. Full Pipeline — CSV to SQLite
# =============================================================================
def test_full_pipeline_csv_to_sqlite(sample_csv_path):
    """
    Integration test: runs the full pipeline from CSV extraction through validation to SQLite load.
    Requires the sample_csv_path fixture and an existing SQLite database.
    """
    from pipeline.ingest import run_csv_pipeline

    db_path = os.environ.get("SQLITE_DB_PATH")
    if not db_path or not os.path.exists(db_path):
        pytest.skip("SQLite database not available for pipeline integration test")

    report = run_csv_pipeline(
        csv_path=sample_csv_path,
        db_path=db_path,
        quarantine_dir=tempfile.mkdtemp(),
        results_dir=tempfile.mkdtemp()
    )

    # CSV has 13 rows total: 10 valid + 3 invalid
    assert report["filas_extraidas"] == 13
    assert report["filas_validas"] == 10
    assert report["filas_rechazadas"] == 3
    assert report["filas_insertadas"] <= 10
    assert report["tiempo_total"] > 0


# =============================================================================
# 6. Pipeline Idempotency
# =============================================================================
def test_pipeline_idempotency(sample_csv_path):
    """
    Verifies that running the pipeline twice with the same data produces the same result.
    Second run should report 0 inserted rows (all duplicates).
    """
    from pipeline.ingest import run_csv_pipeline

    db_path = os.environ.get("SQLITE_DB_PATH")
    if not db_path or not os.path.exists(db_path):
        pytest.skip("SQLite database not available for pipeline idempotency test")

    q_dir = tempfile.mkdtemp()
    r_dir = tempfile.mkdtemp()

    # First run
    report1 = run_csv_pipeline(csv_path=sample_csv_path, db_path=db_path, quarantine_dir=q_dir, results_dir=r_dir)
    inserted_first = report1["filas_insertadas"]

    # Second run with the same CSV (should be all duplicates)
    report2 = run_csv_pipeline(csv_path=sample_csv_path, db_path=db_path, quarantine_dir=q_dir, results_dir=r_dir)
    assert report2["filas_insertadas"] == 0
    assert report2["filas_duplicadas"] == inserted_first + report1["filas_duplicadas"]


# =============================================================================
# 7. POST /pipeline/ingest — Accepts CSV
# =============================================================================
def test_ingest_endpoint_accepts_csv(client, sample_csv_path):
    """Verifies the /pipeline/ingest endpoint processes a CSV file upload."""
    with open(sample_csv_path, "rb") as f:
        response = client.post(
            "/pipeline/ingest",
            files={"file": ("test_transactions.csv", f, "text/csv")}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "report" in data


# =============================================================================
# 8. POST /pipeline/ingest — Returns Report
# =============================================================================
def test_ingest_endpoint_returns_report(client, sample_csv_path):
    """Verifies the ingestion report contains all expected metric fields."""
    with open(sample_csv_path, "rb") as f:
        response = client.post(
            "/pipeline/ingest",
            files={"file": ("test_data.csv", f, "text/csv")}
        )

    assert response.status_code == 200
    report = response.json()["report"]
    assert "filas_extraidas" in report
    assert "filas_validas" in report
    assert "filas_rechazadas" in report
    assert "filas_rechazadas_por_tipo_de_error" in report
    assert "filas_insertadas" in report
    assert "filas_duplicadas" in report
    assert "tiempo_total" in report


# =============================================================================
# 9. POST /pipeline/ingest — Rejects Non-CSV
# =============================================================================
def test_ingest_endpoint_rejects_non_csv(client):
    """Verifies that non-CSV file uploads are rejected with 400."""
    content = b"this is not a csv"
    response = client.post(
        "/pipeline/ingest",
        files={"file": ("data.txt", io.BytesIO(content), "text/plain")}
    )
    assert response.status_code == 400
    assert "Only .csv" in response.json()["detail"]
