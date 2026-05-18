import sqlite3
import duckdb
import time
import json
import argparse
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta

def get_random_params(conn):
    """Fetch some random values from the DB to use in queries."""
    cursor = conn.cursor()
    cursor.execute("SELECT transaction_id, user_id, country_code, timestamp FROM transactions ORDER BY RANDOM() LIMIT 1")
    row = cursor.fetchone()
    
    # Calculate a date range for P3/P4
    ts = datetime.fromisoformat(row[3])
    start_date = (ts - timedelta(days=30)).isoformat()
    end_date = ts.isoformat()
    
    return {
        "transaction_id": row[0],
        "user_id": row[1],
        "country_code": row[2],
        "start_date": start_date,
        "end_date": end_date,
        "last_month": (datetime.now() - timedelta(days=30)).isoformat()
    }

def run_sqlite_query(conn, query, params, label):
    """Runs a query in SQLite and returns execution time and explain plan."""
    # Get explain plan
    explain_cursor = conn.cursor()
    explain_cursor.execute(f"EXPLAIN QUERY PLAN {query}", params)
    plan = "\n".join([row[3] for row in explain_cursor.fetchall()])
    
    # Measure time
    start = time.perf_counter()
    cursor = conn.cursor()
    cursor.execute(query, params)
    results = cursor.fetchall()
    duration = (time.perf_counter() - start) * 1000 # to ms
    
    return duration, plan, len(results)

def run_duckdb_query(duck_conn, query, params):
    """Runs a query in DuckDB (Parquet) and returns execution time."""
    # Convert SQLite named params (:name) to DuckDB named params ($name)
    duck_query = query
    for key in params.keys():
        duck_query = duck_query.replace(f":{key}", f"${key}")
        
    start = time.perf_counter()
    results = duck_conn.execute(duck_query, params).fetchall()
    duration = (time.perf_counter() - start) * 1000 # to ms
    return duration

def benchmark():
    base_dir = Path(__file__).parent.parent
    db_path = base_dir / "data" / "transactions.db"
    parquet_path = base_dir / "data" / "test_1m_snappy.parquet"
    
    if not db_path.exists():
        print("Database not found. Please run ingest.py first.")
        return

    conn = sqlite3.connect(str(db_path))
    duck_conn = duckdb.connect()
    
    # Register parquet in DuckDB
    duck_conn.execute(f"CREATE VIEW transactions AS SELECT * FROM read_parquet('{parquet_path}')")
    
    params = get_random_params(conn)
    print(f"Testing with params: {params}")

    patterns = {
        "P1": ("SELECT * FROM transactions WHERE transaction_id = :transaction_id", {"transaction_id": params["transaction_id"]}),
        "P2": ("SELECT * FROM transactions WHERE user_id = :user_id ORDER BY timestamp DESC LIMIT 20", {"user_id": params["user_id"]}),
        "P3": ("SELECT * FROM transactions WHERE user_id = :user_id AND timestamp BETWEEN :start_date AND :end_date", 
               {"user_id": params["user_id"], "start_date": params["start_date"], "end_date": params["end_date"]}),
        "P4": ("SELECT SUM(amount) FROM transactions WHERE user_id = :user_id AND timestamp >= :last_month", 
               {"user_id": params["user_id"], "last_month": params["last_month"]}),
        "P5": ("SELECT user_id, COUNT(*) as cnt FROM transactions WHERE country_code = :country_code GROUP BY user_id HAVING cnt > 5", 
               {"country_code": params["country_code"]})
    }

    slas = {"P1": 10, "P2": 50, "P3": 50, "P4": 50, "P5": 200}
    
    results = {}

    # 1. Run WITH indices
    print("\n--- Running with indices ---")
    results["with_indices"] = {}
    for id, (query, q_params) in patterns.items():
        dur, plan, count = run_sqlite_query(conn, query, q_params, id)
        results["with_indices"][id] = {"time_ms": dur, "plan": plan, "sla_met": dur < slas[id]}
        print(f"{id}: {dur:.2f}ms (SLA: {slas[id]}ms) - {'PASS' if dur < slas[id] else 'FAIL'}")

    # 2. Run WITHOUT indices (except PK)
    print("\n--- Running without indices ---")
    conn.execute("DROP INDEX IF EXISTS idx_user_timestamp")
    conn.execute("DROP INDEX IF EXISTS idx_country_code")
    
    results["without_indices"] = {}
    for id, (query, q_params) in patterns.items():
        dur, plan, count = run_sqlite_query(conn, query, q_params, id)
        results["without_indices"][id] = {"time_ms": dur, "plan": plan}
        print(f"{id}: {dur:.2f}ms")

    # 3. Run DuckDB (Parquet)
    print("\n--- Running DuckDB (Parquet) ---")
    results["duckdb"] = {}
    for id, (query, q_params) in patterns.items():
        # DuckDB uses $1, $2 or :name
        dur = run_duckdb_query(duck_conn, query, q_params)
        results["duckdb"][id] = {"time_ms": dur}
        print(f"{id}: {dur:.2f}ms")

    # Restore indices for future use
    print("\nRestoring indices...")
    conn.execute("CREATE INDEX idx_user_timestamp ON transactions (user_id, timestamp DESC)")
    conn.execute("CREATE INDEX idx_country_code ON transactions (country_code)")
    
    conn.close()

    # Save results
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    with open(results_dir / "query_benchmarks.json", "w") as f:
        json.dump(results, f, indent=4)
    print(f"\nResults saved to {results_dir / 'query_benchmarks.json'}")

if __name__ == "__main__":
    benchmark()
