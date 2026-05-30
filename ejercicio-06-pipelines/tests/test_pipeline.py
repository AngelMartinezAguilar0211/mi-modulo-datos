import os
import sqlite3
import json
import uuid
import pytest
from datetime import datetime, timezone, timedelta

from data_source import generate_batch
from extract import extract_and_normalize
from transform import transform_and_validate
from load import load_to_sqlite, init_database
from pipeline import run_pipeline

@pytest.fixture
def temp_dirs(tmp_path):
    """
    Fixture that creates isolated temporary directories for the database,
    quarantine files, and results reports during test execution.
    """
    db_file = tmp_path / "test_transactions.db"
    quarantine_dir = tmp_path / "quarantine"
    results_dir = tmp_path / "results"
    
    quarantine_dir.mkdir()
    results_dir.mkdir()
    
    # Initialize the temporary database structure
    init_database(str(db_file))
    
    return {
        "db_path": str(db_file),
        "quarantine_dir": str(quarantine_dir),
        "results_dir": str(results_dir)
    }

def test_happy_path(temp_dirs):
    """
    1. HAPPY PATH SCENARIO:
    Inject 100% valid transactions. They must pass all ETL layers,
    persist fully in the SQLite database, and yield correct metric counts.
    """
    valid_tx = {
        "transaction_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": 1234,
        "merchant_id": 5678,
        "amount": 99.95,
        "category": "Electronics",
        "country_code": "MX",
        "status": "completed"
    }
    
    # Execute extraction/normalization, validation, and load directly
    normalized = extract_and_normalize([valid_tx])
    valid, rejected, errors = transform_and_validate(normalized, quarantine_dir=temp_dirs["quarantine_dir"])
    
    assert len(valid) == 1
    assert len(rejected) == 0
    assert sum(errors.values()) == 0
    
    inserted, duplicates = load_to_sqlite(valid, temp_dirs["db_path"])
    assert inserted == 1
    assert duplicates == 0
    
    # Verify persistence in the SQLite database
    conn = sqlite3.connect(temp_dirs["db_path"])
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE transaction_id = ?", (valid_tx["transaction_id"],))
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    assert row[2] == 1234  # user_id
    assert row[4] == 99.95  # amount

def test_validation_and_quarantine(temp_dirs):
    """
    2. VALIDATION AND QUARANTINE SCENARIO:
    Inject multiple deliberately malformed transactions to check that
    they are correctly intercepted by each business rule and sent to quarantine.
    """
    bad_transactions = [
        # a) amount out of range
        {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": 1,
            "merchant_id": 1,
            "amount": -10.0,
            "category": "Food",
            "country_code": "MX",
            "status": "completed"
        },
        # b) invalid category
        {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": 1,
            "merchant_id": 1,
            "amount": 100.0,
            "category": "Gambling",
            "country_code": "MX",
            "status": "completed"
        },
        # c) invalid country_code
        {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": 1,
            "merchant_id": 1,
            "amount": 50.0,
            "category": "Food",
            "country_code": "US",
            "status": "completed"
        },
        # d) future timestamp
        {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat(),
            "user_id": 1,
            "merchant_id": 1,
            "amount": 25.0,
            "category": "Food",
            "country_code": "CO",
            "status": "completed"
        },
        # e) malformed UUID
        {
            "transaction_id": "not-a-uuid",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": 1,
            "merchant_id": 1,
            "amount": 15.0,
            "category": "Food",
            "country_code": "CL",
            "status": "completed"
        },
        # f) missing/null field
        {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": None,
            "merchant_id": 1,
            "amount": 100.00,
            "category": "Food",
            "country_code": "MX",
            "status": "completed"
        }
    ]
    
    normalized = extract_and_normalize(bad_transactions)
    valid, rejected, errors = transform_and_validate(normalized, quarantine_dir=temp_dirs["quarantine_dir"])
    
    # All must have been rejected
    assert len(valid) == 0
    assert len(rejected) == 6
    
    # Verify error metrics desaggregation
    assert errors["amount_out_of_range"] == 1
    assert errors["invalid_category"] == 1
    assert errors["invalid_country"] == 1
    assert errors["future_timestamp"] == 1
    assert errors["invalid_uuid"] == 1
    assert errors["missing_fields"] == 1
    
    # Verify physical creation of the quarantine JSONLines file
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    quarantine_file = os.path.join(temp_dirs["quarantine_dir"], f"{today_str}.jsonl")
    assert os.path.exists(quarantine_file)
    
    # Read the quarantine file and validate its internal structure
    with open(quarantine_file, "r") as f:
        lines = f.readlines()
        
    assert len(lines) == 6
    first_entry = json.loads(lines[0])
    assert "transaction" in first_entry
    assert "rejection_reasons" in first_entry
    assert "quarantined_at" in first_entry
    assert "amount_out_of_range" in first_entry["rejection_reasons"]

def test_idempotency(temp_dirs):
    """
    3. IDEMPOTENCY SCENARIO:
    Loading the exact same batch of valid transactions twice must result
    in N insertions during the first run, and 0 insertions during the second run
    (all counted as duplicates) without altering database state.
    """
    tx_lote = [
        {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": 44,
            "merchant_id": 55,
            "amount": 120.50,
            "category": "Food",
            "country_code": "CO",
            "status": "completed"
        },
        {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": 99,
            "merchant_id": 77,
            "amount": 350.00,
            "category": "Travel",
            "country_code": "BR",
            "status": "completed"
        }
    ]
    
    # Run 1
    inserted_1, duplicates_1 = load_to_sqlite(tx_lote, temp_dirs["db_path"])
    assert inserted_1 == 2
    assert duplicates_1 == 0
    
    # Run 2 (same data)
    inserted_2, duplicates_2 = load_to_sqlite(tx_lote, temp_dirs["db_path"])
    assert inserted_2 == 0
    assert duplicates_2 == 2

def test_transactional_atomicity(temp_dirs):
    """
    4. TRANSACTIONAL ATOMICITY SCENARIO:
    If any database error occurs mid-load, the database must not save
    ANY records from the current batch (full rollback).
    """
    tx_lote = [
        {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": 10,
            "merchant_id": 20,
            "amount": 100.00,
            "category": "Food",
            "country_code": "MX",
            "status": "completed"
        },
        {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": 30,
            "merchant_id": 40,
            "amount": 200.00,
            "category": "Health",
            "country_code": "BR",
            "status": "completed"
        }
    ]
    
    # Execute loading forcing a simulated database failure at index 1
    with pytest.raises(RuntimeError) as excinfo:
        load_to_sqlite(tx_lote, temp_dirs["db_path"], force_error_at=1)
        
    assert "Simulated database failure" in str(excinfo.value)
    
    # Verify that NO transactions from the batch were saved (successful rollback)
    conn = sqlite3.connect(temp_dirs["db_path"])
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM transactions WHERE user_id IN (10, 30)")
    count = cursor.fetchone()[0]
    conn.close()
    
    assert count == 0  # Absolute transactional atomicity: all or nothing!

def test_pipeline_orchestration(temp_dirs):
    """
    Verifies that the run_pipeline orchestrator chains all phases
    and saves a structured metric JSON report.
    """
    report = run_pipeline(
        batch_size=50,
        error_rate=0.2,
        db_path=temp_dirs["db_path"],
        quarantine_dir=temp_dirs["quarantine_dir"],
        results_dir=temp_dirs["results_dir"]
    )
    
    # Validate essential report fields
    assert report["filas_extraidas"] == 50
    assert report["filas_validas"] + report["filas_rechazadas"] == 50
    assert report["filas_insertadas"] + report["filas_duplicadas"] == report["filas_validas"]
    assert report["tiempo_total"] > 0
    
    # Check that the metric report JSON file was physically saved
    results_files = os.listdir(temp_dirs["results_dir"])
    assert len(results_files) == 1
    assert results_files[0].startswith("run_")
    assert results_files[0].endswith(".json")
    
    # Read and parse the saved report
    report_file_path = os.path.join(temp_dirs["results_dir"], results_files[0])
    with open(report_file_path, "r") as f:
        saved_report = json.load(f)
        
    assert saved_report["run_id"] == report["run_id"]
    assert saved_report["filas_extraidas"] == 50
