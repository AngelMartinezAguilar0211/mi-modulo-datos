import sqlite3
import pandas as pd
import argparse
import time
import os
from pathlib import Path

def setup_database(db_path, schema_path):
    """Initializes the database with the schema."""
    if os.path.exists(db_path):
        os.remove(db_path)
    
    with sqlite3.connect(db_path) as conn:
        with open(schema_path, 'r') as f:
            conn.executescript(f.read())
    print(f"Database initialized at {db_path}")

def ingest_data(db_path, parquet_path, chunk_size, use_wal):
    """Ingests data from Parquet to SQLite in chunks."""
    start_time = time.perf_counter()
    
    # Read the parquet file
    print(f"Reading {parquet_path}...")
    df = pd.read_parquet(parquet_path)
    total_records = len(df)
    
    conn = sqlite3.connect(db_path)
    
    if use_wal:
        conn.execute("PRAGMA journal_mode=WAL;")
        print("WAL mode enabled.")
    
    # SQLite optimization settings
    conn.execute("PRAGMA synchronous=OFF;")
    conn.execute("PRAGMA cache_size=10000;")
    
    try:
        cursor = conn.cursor()
        
        # Ingest in chunks
        for i in range(0, total_records, chunk_size):
            chunk = df.iloc[i:i+chunk_size]
            
            # Start transaction
            cursor.execute("BEGIN TRANSACTION;")
            
            # Insert chunk
            chunk.to_sql('transactions', conn, if_exists='append', index=False)
            
            # Commit transaction
            conn.commit()
            
            if (i + chunk_size) % 100000 == 0 or (i + chunk_size) >= total_records:
                print(f"Ingested {min(i + chunk_size, total_records)} / {total_records} records...")
                
    except Exception as e:
        conn.rollback()
        print(f"Error during ingestion: {e}")
        raise
    finally:
        conn.close()
        
    end_time = time.perf_counter()
    duration = end_time - start_time
    print(f"Ingestion completed in {duration:.2f} seconds.")
    return duration

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest transactions from Parquet to SQLite.")
    parser.add_argument("--chunk-size", type=int, default=50000, help="Number of rows per transaction.")
    parser.add_argument("--wal", action="store_true", help="Enable Write-Ahead Logging.")
    parser.add_argument("--no-wal", action="store_false", dest="wal", help="Disable Write-Ahead Logging.")
    parser.set_defaults(wal=True)
    
    args = parser.parse_args()
    
    # Paths
    base_dir = Path(__file__).parent.parent
    db_path = base_dir / "data" / "transactions.db"
    schema_path = Path(__file__).parent / "schema.sql"
    parquet_path = base_dir / "data" / "test_1m_snappy.parquet"
    
    if not parquet_path.exists():
        print(f"Error: Source file not found at {parquet_path}")
        exit(1)
        
    setup_database(str(db_path), str(schema_path))
    duration = ingest_data(str(db_path), str(parquet_path), args.chunk_size, args.wal)
    
    # Save results
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    
    import json
    with open(results_dir / "ingest_results.json", "w") as f:
        json.dump({
            "duration_seconds": duration,
            "chunk_size": args.chunk_size,
            "wal_enabled": args.wal,
            "records": 1000000
        }, f, indent=4)
