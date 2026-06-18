import pytest
import os
import uuid
import csv
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

# Set default test environment variables before importing the app
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent

# Create a temporary SQLite database specifically for running tests.
# This avoids writing to the production database and prevents permission/read-only issues.
import sqlite3
test_db_fd, test_db_path = tempfile.mkstemp(suffix=".db", prefix="test_transactions_")
os.close(test_db_fd)

# Initialize the schema in the temporary database
conn = sqlite3.connect(test_db_path)
conn.execute("""
CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    user_id INTEGER NOT NULL,
    merchant_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    category TEXT NOT NULL,
    country_code TEXT NOT NULL,
    status TEXT NOT NULL
);
""")
conn.execute("CREATE INDEX idx_user_timestamp ON transactions (user_id, timestamp DESC);")
conn.execute("CREATE INDEX idx_country_code ON transactions (country_code);")
conn.execute("CREATE INDEX idx_status_timestamp ON transactions (status, timestamp);")
conn.commit()
conn.close()

# Force the application to use this temporary SQLite database
os.environ["SQLITE_DB_PATH"] = test_db_path
os.environ.setdefault("PARQUET_FILE_PATH", str(project_root / "data" / "test_1m_snappy.parquet"))

from app.main import app
from app.cache import cache


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    yield
    # Cleanup the temp database after all tests complete
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
            # Clean up WAL/journal files if any exist
            for ext in (".db-shm", ".db-wal", "-shm", "-wal"):
                for p in (test_db_path + ext, test_db_path.replace(".db", ext)):
                    if os.path.exists(p):
                        os.remove(p)
        except Exception:
            pass


@pytest.fixture(scope="module")
def client():
    """FastAPI test client with lifespan events triggered."""
    with TestClient(app) as c:
        cache.clear()
        yield c


@pytest.fixture
def sample_csv_path(tmp_path):
    """
    Generates a temporary CSV file with a mix of valid and invalid transactions
    for pipeline integration tests.
    """
    csv_file = tmp_path / "test_transactions.csv"
    rows = [
        # 10 valid transactions
        *[
            {
                "transaction_id": str(uuid.uuid4()),
                "timestamp": "2026-06-10T10:00:00Z",
                "user_id": str(i + 1),
                "merchant_id": str(100 + i),
                "amount": str(round(50.0 + i * 10, 2)),
                "category": "Food",
                "country_code": "MX",
                "status": "completed"
            }
            for i in range(10)
        ],
        # 3 invalid transactions (for quarantine testing)
        {
            "transaction_id": "not-a-valid-uuid",
            "timestamp": "2026-06-10T10:00:00Z",
            "user_id": "1",
            "merchant_id": "100",
            "amount": "50.00",
            "category": "Food",
            "country_code": "MX",
            "status": "completed"
        },
        {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": "2026-06-10T10:00:00Z",
            "user_id": "1",
            "merchant_id": "100",
            "amount": "-999.99",
            "category": "Food",
            "country_code": "MX",
            "status": "completed"
        },
        {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": "2026-06-10T10:00:00Z",
            "user_id": "1",
            "merchant_id": "100",
            "amount": "50.00",
            "category": "Gambling",
            "country_code": "MX",
            "status": "completed"
        },
    ]

    fieldnames = ["transaction_id", "timestamp", "user_id", "merchant_id", "amount", "category", "country_code", "status"]

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return str(csv_file)
