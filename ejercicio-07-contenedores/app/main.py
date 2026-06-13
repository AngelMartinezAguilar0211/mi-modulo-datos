from fastapi import FastAPI, HTTPException, Query, Path as FastAPIPath
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# --- JSON Logging Configuration ---
class JSONFormatter(logging.Formatter):
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
    # Force json output for root and common uvicorn loggers
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

# Active HTTP request tracker
active_requests = 0

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing API application lifespan...")
    
    # Locate paths from environment variables or project fallback folders
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent.parent
    
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
    title="Transactional and Analytics API (Containerized)",
    description="Dual SQLite/DuckDB backend API optimized for high performance OLAP/OLTP inside Docker.",
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

# --- Endpoints ---

# 1. GET /analytics/summary
@app.get("/analytics/summary")
def get_analytics_summary():
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
        raise HTTPException(status_code=500, detail="DuckDB analytical query failed")

# 2. GET /analytics/top-merchants
@app.get("/analytics/top-merchants")
def get_top_merchants(
    limit: int = Query(10, ge=1),
    country: Optional[str] = Query(None, min_length=2, max_length=2)
):
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
        raise HTTPException(status_code=500, detail="DuckDB analytical query failed")

# 3. GET /users/{user_id}/transactions
@app.get("/users/{user_id}/transactions")
def get_user_transactions(
    user_id: int = FastAPIPath(..., ge=1, le=50000),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    try:
        conn = db_manager.get_sqlite_conn()
        cursor = conn.cursor()
        
        # Check total transaction count for this user
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE user_id = ?;", (user_id,))
        total_records = cursor.fetchone()[0]
        
        if total_records == 0:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found or has no transactions.")
            
        total_pages = (total_records + page_size - 1) // page_size
        
        if page > total_pages:
            raise HTTPException(status_code=400, detail=f"Page {page} is out of range. Total pages: {total_pages}.")
            
        offset = (page - 1) * page_size
        cursor.execute(
            """
            SELECT * FROM transactions
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?;
            """,
            (user_id, page_size, offset)
        )
        
        rows = cursor.fetchall()
        transactions = [dict(row) for row in rows]
        
        return {
            "user_id": user_id,
            "page": page,
            "page_size": page_size,
            "total_records": total_records,
            "total_pages": total_pages,
            "transactions": transactions
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SQLite transactions query failed for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="SQLite database query failed")

# 4. GET /users/{user_id}/stats
@app.get("/users/{user_id}/stats")
def get_user_stats(
    user_id: int = FastAPIPath(..., ge=1, le=50000)
):
    try:
        conn = db_manager.get_sqlite_conn()
        cursor = conn.cursor()
        
        # 1. Total count and sum
        cursor.execute("SELECT COUNT(*), SUM(amount) FROM transactions WHERE user_id = ?;", (user_id,))
        cnt, total_amt = cursor.fetchone()
        
        if cnt == 0 or cnt is None:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found or has no transactions.")
            
        # 2. Most frequent category
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
        
        # 3. User's primary country code
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
        raise HTTPException(status_code=500, detail="SQLite database query failed")

# 5. POST /transactions/batch (Idempotent and Auditable)
@app.post("/transactions/batch")
def create_transactions_batch(
    batch: List[TransactionModel]
):
    # Enforce maximum batch size limit of 500 records
    if len(batch) > 500:
        raise HTTPException(status_code=400, detail="Batch size exceeds maximum limit of 500 transactions.")
        
    if not batch:
        raise HTTPException(status_code=400, detail="Empty transaction batch.")

    # Deduplicate batch in-memory based on transaction_id (keeping the last occurrence in the batch)
    seen = {}
    for tx in batch:
        seen[tx.transaction_id] = tx
    unique_txs = list(seen.values())
    
    try:
        conn = db_manager.get_sqlite_conn()
        cursor = conn.cursor()
        
        # Check which IDs already exist in the database to prevent silent updates (auditing integrity)
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
        except:
            pass
        logger.error(f"SQLite transaction insert failed: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")

# 6. GET /health
@app.get("/health")
def get_system_health():
    uptime_seconds = time.time() - app.state.start_time
    metrics = cache.metrics
    
    sqlite_ok = False
    try:
        conn = db_manager.get_sqlite_conn()
        conn.execute("SELECT 1;")
        sqlite_ok = True
    except:
        pass
        
    duckdb_ok = False
    try:
        cursor = db_manager.get_duckdb_cursor()
        cursor.execute("SELECT 1;")
        duckdb_ok = True
    except:
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
