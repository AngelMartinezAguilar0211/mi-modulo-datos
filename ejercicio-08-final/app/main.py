from fastapi import FastAPI, HTTPException, Query, Path as FastAPIPath, UploadFile, File
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
import os
import sys
import json
import uuid
import logging
import tempfile
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# --- JSON Logging Configuration ---
class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects for structured logging."""
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def setup_json_logging():
    """Force JSON output for root and common uvicorn loggers."""
    for logger_name in ("", "uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(logger_name)
        # Remove existing standard output handlers
        for handler in list(logger.handlers):
            logger.removeHandler(handler)

        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False


# Setup JSON logging immediately upon module import
setup_json_logging()
logger = logging.getLogger("api_app")

# Import db_manager and other components after logging setup
from app.db import db_manager
from app.cache import cache
from app.models import TransactionModel

# Environment configurations with fallback defaults
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))
ANOMALY_DEFAULT_THRESHOLD = int(os.getenv("ANOMALY_DEFAULT_THRESHOLD", "5"))

# Maximum uploaded CSV file size: 50 MB
MAX_CSV_UPLOAD_BYTES = 50 * 1024 * 1024

# Active HTTP request tracker
active_requests = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application startup (DB init, cache warm) and shutdown (connection cleanup)."""
    logger.info("Initializing API application lifespan...")

    sqlite_path = os.getenv("SQLITE_DB_PATH")
    parquet_path = os.getenv("PARQUET_FILE_PATH")

    # Initialize connection pools with validation checks
    db_manager.init_db(sqlite_path, parquet_path)

    # Pre-warm DuckDB columnar engine to prevent first request cold latency
    logger.info("Pre-warming DuckDB transactional cache...")
    try:
        cursor = db_manager.get_duckdb_cursor()
        cursor.execute("SELECT COUNT(*) FROM transactions_view;")
        count_res = cursor.fetchone()[0]
        logger.info(f"DuckDB cache pre-warmed successfully. Parquet rows loaded: {count_res}")
    except Exception as e:
        logger.error(f"Failed to pre-warm DuckDB cache: {e}")

    # Track server start time
    app.state.start_time = time.time()

    yield
    # Cleanup database connections gracefully
    logger.info("Shutting down API application, closing database connections...")
    db_manager.close()


app = FastAPI(
    title="Sistema de Monitoreo Transaccional — Fintech LATAM",
    description="Dual SQLite/DuckDB backend API with CSV pipeline ingestion and anomaly detection.",
    version="1.0.0",
    lifespan=lifespan
)


# Middleware to track current active connections
@app.middleware("http")
async def monitor_active_connections(request, call_next):
    global active_requests
    active_requests += 1
    try:
        response = await call_next(request)
        return response
    finally:
        active_requests -= 1


# =============================================================================
# ENDPOINT 1: GET /analytics/summary
# =============================================================================
@app.get("/analytics/summary")
def get_analytics_summary():
    """Returns global transaction volume breakdown by country and category (DuckDB/Parquet)."""
    cache_key = "analytics_summary"
    cached_res = cache.get(cache_key)
    if cached_res:
        return cached_res

    try:
        cursor = db_manager.get_duckdb_cursor()

        # Query global totals from parquet view
        cursor.execute("SELECT COUNT(*), SUM(amount), AVG(amount) FROM transactions_view;")
        total_cnt, total_amt, avg_amt = cursor.fetchone()

        # Query breakdown by country
        cursor.execute("SELECT country_code, COUNT(*), SUM(amount) FROM transactions_view GROUP BY country_code;")
        country_rows = cursor.fetchall()
        breakdown_by_country = {
            row[0]: {"count": row[1], "amount": float(row[2])} for row in country_rows
        }

        # Query breakdown by category
        cursor.execute("SELECT category, COUNT(*), SUM(amount) FROM transactions_view GROUP BY category;")
        category_rows = cursor.fetchall()
        breakdown_by_category = {
            row[0]: {"count": row[1], "amount": float(row[2])} for row in category_rows
        }

        result = {
            "total_count": int(total_cnt) if total_cnt is not None else 0,
            "total_amount": float(total_amt) if total_amt is not None else 0.0,
            "avg_amount": float(avg_amt) if avg_amt is not None else 0.0,
            "breakdown_by_country": breakdown_by_country,
            "breakdown_by_category": breakdown_by_category
        }

        cache.set(cache_key, result, CACHE_TTL)
        return result
    except Exception as e:
        logger.error(f"DuckDB analytical summary query failed: {e}")
        raise HTTPException(status_code=500, detail="Analytical query failed")


# =============================================================================
# ENDPOINT 2: GET /analytics/top-merchants
# =============================================================================
@app.get("/analytics/top-merchants")
def get_top_merchants(
    limit: int = Query(10, ge=1),
    country: Optional[str] = Query(None, min_length=2, max_length=2)
):
    """Returns top merchants ranked by transaction volume (DuckDB/Parquet)."""
    country_upper = country.upper() if country else None
    cache_key = f"analytics_top_merchants_limit_{limit}_country_{country_upper}"

    cached_res = cache.get(cache_key)
    if cached_res:
        return cached_res

    try:
        cursor = db_manager.get_duckdb_cursor()

        if country_upper:
            cursor.execute(
                """
                SELECT merchant_id, SUM(amount) as volume, COUNT(*) as tx_count
                FROM transactions_view
                WHERE country_code = ?
                GROUP BY merchant_id
                ORDER BY volume DESC
                LIMIT ?;
                """,
                (country_upper, limit)
            )
        else:
            cursor.execute(
                """
                SELECT merchant_id, SUM(amount) as volume, COUNT(*) as tx_count
                FROM transactions_view
                GROUP BY merchant_id
                ORDER BY volume DESC
                LIMIT ?;
                """,
                (limit,)
            )

        rows = cursor.fetchall()
        result = [
            {
                "merchant_id": int(row[0]),
                "volume": float(row[1]),
                "transaction_count": int(row[2])
            }
            for row in rows
        ]

        cache.set(cache_key, result, CACHE_TTL)
        return result
    except Exception as e:
        logger.error(f"DuckDB top merchants query failed: {e}")
        raise HTTPException(status_code=500, detail="Analytical query failed")


# =============================================================================
# ENDPOINT 3: GET /users/{user_id}/transactions (with date filters)
# =============================================================================
@app.get("/users/{user_id}/transactions")
def get_user_transactions(
    user_id: int = FastAPIPath(..., ge=1, le=50000),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    date_from: Optional[str] = Query(None, description="Filter start date (ISO 8601, e.g. 2026-01-01)"),
    date_to: Optional[str] = Query(None, description="Filter end date (ISO 8601, e.g. 2026-12-31)")
):
    """Returns paginated transaction history for a user, with optional date range filters."""
    try:
        conn = db_manager.get_sqlite_conn()
        cursor = conn.cursor()

        # Build dynamic WHERE clause with parameterized queries
        conditions = ["user_id = ?"]
        params: list = [user_id]

        if date_from:
            conditions.append("timestamp >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("timestamp <= ?")
            params.append(date_to)

        where_clause = " AND ".join(conditions)

        # Check total transaction count for this user (with filters)
        cursor.execute(f"SELECT COUNT(*) FROM transactions WHERE {where_clause};", params)
        total_records = cursor.fetchone()[0]

        if total_records == 0:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found or has no transactions matching the filters.")

        total_pages = (total_records + page_size - 1) // page_size

        if page > total_pages:
            raise HTTPException(status_code=400, detail=f"Page {page} is out of range. Total pages: {total_pages}.")

        offset = (page - 1) * page_size
        cursor.execute(
            f"""
            SELECT * FROM transactions
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?;
            """,
            params + [page_size, offset]
        )

        rows = cursor.fetchall()
        transactions = [dict(row) for row in rows]

        return {
            "user_id": user_id,
            "page": page,
            "page_size": page_size,
            "total_records": total_records,
            "total_pages": total_pages,
            "filters": {
                "date_from": date_from,
                "date_to": date_to
            },
            "transactions": transactions
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SQLite transactions query failed for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Database query failed")


# =============================================================================
# ENDPOINT 4: GET /users/{user_id}/stats
# =============================================================================
@app.get("/users/{user_id}/stats")
def get_user_stats(
    user_id: int = FastAPIPath(..., ge=1, le=50000)
):
    """Returns aggregated statistics for a specific user (SQLite)."""
    try:
        conn = db_manager.get_sqlite_conn()
        cursor = conn.cursor()

        # Total count and sum
        cursor.execute("SELECT COUNT(*), SUM(amount) FROM transactions WHERE user_id = ?;", (user_id,))
        cnt, total_amt = cursor.fetchone()

        if cnt == 0 or cnt is None:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found or has no transactions.")

        # Most frequent category
        cursor.execute(
            """
            SELECT category, COUNT(*) as freq
            FROM transactions
            WHERE user_id = ?
            GROUP BY category
            ORDER BY freq DESC, category ASC
            LIMIT 1;
            """,
            (user_id,)
        )
        cat_row = cursor.fetchone()
        most_frequent_category = cat_row[0] if cat_row else "N/A"

        # User's primary country code
        cursor.execute(
            """
            SELECT country_code, COUNT(*) as freq
            FROM transactions
            WHERE user_id = ?
            GROUP BY country_code
            ORDER BY freq DESC, country_code ASC
            LIMIT 1;
            """,
            (user_id,)
        )
        c_row = cursor.fetchone()
        country_code = c_row[0] if c_row else "N/A"

        return {
            "user_id": user_id,
            "total_amount": float(total_amt) if total_amt is not None else 0.0,
            "transaction_count": int(cnt),
            "most_frequent_category": most_frequent_category,
            "country_code": country_code
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SQLite stats query failed for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Database query failed")


# =============================================================================
# ENDPOINT 5: POST /transactions/batch (Idempotent)
# =============================================================================
@app.post("/transactions/batch")
def create_transactions_batch(
    batch: List[TransactionModel]
):
    """Inserts a batch of transactions idempotently. Duplicates are ignored without overwriting."""
    # Enforce maximum batch size limit of 500 records
    if len(batch) > 500:
        raise HTTPException(status_code=400, detail="Batch size exceeds maximum limit of 500 transactions.")

    if not batch:
        raise HTTPException(status_code=400, detail="Empty transaction batch.")

    # Deduplicate batch in-memory based on transaction_id (keeping the last occurrence)
    seen = {}
    for tx in batch:
        seen[tx.transaction_id] = tx
    unique_txs = list(seen.values())

    try:
        conn = db_manager.get_sqlite_conn()
        cursor = conn.cursor()

        # Check which IDs already exist in the database to prevent silent updates
        tx_ids = [tx.transaction_id for tx in unique_txs]
        placeholders = ",".join("?" for _ in tx_ids)
        cursor.execute(f"SELECT transaction_id FROM transactions WHERE transaction_id IN ({placeholders});", tx_ids)
        existing_ids = {row[0] for row in cursor.fetchall()}

        # Filter transactions that do not exist yet in the database
        to_insert = [tx for tx in unique_txs if tx.transaction_id not in existing_ids]

        if to_insert:
            # Execute insert within an explicit single transaction block
            cursor.execute("BEGIN TRANSACTION;")
            for tx in to_insert:
                cursor.execute(
                    """
                    INSERT INTO transactions
                    (transaction_id, timestamp, user_id, merchant_id, amount, category, country_code, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        tx.transaction_id,
                        tx.timestamp.isoformat() if hasattr(tx.timestamp, "isoformat") else str(tx.timestamp),
                        tx.user_id,
                        tx.merchant_id,
                        tx.amount,
                        tx.category,
                        tx.country_code,
                        tx.status
                    )
                )
            conn.commit()
            logger.info(f"Successfully inserted {len(to_insert)} new transactions. Ignored duplicates: {len(existing_ids)}")

        return {
            "status": "success",
            "received_records": len(batch),
            "inserted_records": len(to_insert),
            "ignored_records": len(existing_ids),
            "ignored_ids": list(existing_ids)
        }
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"SQLite transaction insert failed: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")


# =============================================================================
# ENDPOINT 6: GET /health
# =============================================================================
@app.get("/health")
def get_system_health():
    """Returns system health status including DB connectivity, cache metrics, and uptime."""
    uptime_seconds = time.time() - app.state.start_time
    metrics = cache.metrics

    sqlite_ok = False
    try:
        conn = db_manager.get_sqlite_conn()
        conn.execute("SELECT 1;")
        sqlite_ok = True
    except Exception:
        pass

    duckdb_ok = False
    try:
        cursor = db_manager.get_duckdb_cursor()
        cursor.execute("SELECT 1;")
        duckdb_ok = True
    except Exception:
        pass

    return {
        "status": "healthy" if (sqlite_ok and duckdb_ok) else "degraded",
        "connections_active": active_requests,
        "cache_hit_rate": metrics["hit_rate"],
        "cache_hits": metrics["hits"],
        "cache_misses": metrics["misses"],
        "uptime_seconds": round(uptime_seconds, 2),
        "sqlite_connected": sqlite_ok,
        "duckdb_connected": duckdb_ok
    }


# =============================================================================
# ENDPOINT 7: GET /analytics/anomalies (NEW)
# =============================================================================
@app.get("/analytics/anomalies")
def get_anomalies(
    threshold: int = Query(
        default=None,
        ge=1,
        description="Minimum number of failed transactions in last 30 days to flag a user"
    )
):
    """
    Detects users with anomalous patterns: more than N failed transactions in the last 30 days.
    The threshold N is parameterizable via query parameter (defaults to ANOMALY_DEFAULT_THRESHOLD env var).
    """
    effective_threshold = threshold if threshold is not None else ANOMALY_DEFAULT_THRESHOLD

    try:
        conn = db_manager.get_sqlite_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT user_id, COUNT(*) as failed_count
            FROM transactions
            WHERE status = 'failed'
              AND timestamp >= datetime('now', '-30 days')
            GROUP BY user_id
            HAVING COUNT(*) > ?
            ORDER BY failed_count DESC;
            """,
            (effective_threshold,)
        )

        rows = cursor.fetchall()
        anomalies = [
            {"user_id": row[0], "failed_count": row[1]}
            for row in rows
        ]

        return {
            "threshold": effective_threshold,
            "period_days": 30,
            "total_flagged_users": len(anomalies),
            "anomalies": anomalies
        }
    except Exception as e:
        logger.error(f"Anomaly detection query failed: {e}")
        raise HTTPException(status_code=500, detail="Anomaly detection query failed")


# =============================================================================
# ENDPOINT 8: POST /pipeline/ingest (NEW)
# =============================================================================
@app.post("/pipeline/ingest")
async def ingest_csv(
    file: UploadFile = File(..., description="CSV file with transactions to ingest")
):
    """
    Receives a CSV file, runs the ETL pipeline (extract → transform → load),
    and returns an ingestion report with metrics.
    """
    # Validate file extension (allow-list: only .csv files)
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    # Validate file size by reading content with a size cap
    content = await file.read()
    if len(content) > MAX_CSV_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"File exceeds maximum size of {MAX_CSV_UPLOAD_BYTES // (1024*1024)} MB.")

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded CSV file is empty.")

    # Generate a unique temporary filename to avoid path traversal
    temp_filename = f"ingest_{uuid.uuid4().hex}.csv"
    # Store temporary file inside a controlled directory within the app workspace
    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "temp_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, temp_filename)

    try:
        # Write uploaded content to a secure temporary file
        with open(temp_path, "wb") as f:
            f.write(content)

        # Import and execute the pipeline orchestrator
        from pipeline.ingest import run_csv_pipeline

        sqlite_path = os.getenv("SQLITE_DB_PATH")
        if not sqlite_path:
            raise HTTPException(status_code=500, detail="SQLITE_DB_PATH environment variable is not configured.")

        # Resolve quarantine and results directories
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(base_dir)
        quarantine_dir = os.path.join(project_dir, "quarantine")
        results_dir = os.path.join(project_dir, "results")

        report = run_csv_pipeline(
            csv_path=temp_path,
            db_path=sqlite_path,
            quarantine_dir=quarantine_dir,
            results_dir=results_dir
        )

        logger.info(f"Pipeline ingestion completed: {report.get('filas_insertadas', 0)} rows inserted from {file.filename}")

        return {
            "status": "success",
            "source_file": file.filename,
            "report": report
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pipeline ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline ingestion failed: {str(e)}")
    finally:
        # Always clean up the temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)
