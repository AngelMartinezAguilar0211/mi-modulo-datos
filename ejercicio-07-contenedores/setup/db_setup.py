import sqlite3
import duckdb
import os
import sys
import time

def setup_database():
    sqlite_db_path = os.getenv("SQLITE_DB_PATH")
    parquet_path = os.getenv("PARQUET_FILE_PATH")

    if not sqlite_db_path:
        print("CRITICAL ERROR: Environment variable SQLITE_DB_PATH is not set.")
        sys.exit(1)
        
    if not parquet_path:
        print("CRITICAL ERROR: Environment variable PARQUET_FILE_PATH is not set.")
        sys.exit(1)

    print("==================================================")
    print("STARTING DATABASE SETUP & INGESTION")
    print(f"Target SQLite: {sqlite_db_path}")
    print(f"Source Parquet: {parquet_path}")
    print("==================================================")

    if not os.path.exists(parquet_path):
        print(f"CRITICAL ERROR: Source Parquet file not found at: {parquet_path}")
        sys.exit(1)

    # 1. Initialize SQLite Database & Schema
    # If DB exists, let's keep it or recreate? The exercise states:
    # "setup — servicio que corre una sola vez para crear la base SQLite desde el Parquet"
    # To ensure idempotency and cleanliness, we can recreate or verify. Recreating guarantees a clean slate!
    if os.path.exists(sqlite_db_path):
        print(f"Existing SQLite DB found at {sqlite_db_path}. Removing it to rebuild a clean state...")
        try:
            os.remove(sqlite_db_path)
        except Exception as e:
            print(f"Warning: Could not remove existing DB: {e}. Attempting overwrite.")

    try:
        conn = sqlite3.connect(sqlite_db_path)
        
        # SQLite optimization pragmas for fast loading
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=OFF;")
        conn.execute("PRAGMA cache_size=10000;")
        
        # Create Table matching E03 and E04 specifications
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
        
        # Composite Covering Index for P2, P3, P4
        conn.execute("CREATE INDEX idx_user_timestamp ON transactions (user_id, timestamp DESC);")
        # Filtering/Grouping Index for P5
        conn.execute("CREATE INDEX idx_country_code ON transactions (country_code);")
        
        print("SQLite table schema and indices created successfully.")
    except Exception as e:
        print(f"CRITICAL ERROR creating SQLite schema: {e}")
        sys.exit(1)

    # 2. Ingest Data from Parquet using DuckDB (no Pandas/PyArrow memory bloat)
    start_time = time.time()
    try:
        duck_conn = duckdb.connect()
        # Query matching exact schema column order
        res = duck_conn.execute(
            f"""
            SELECT 
                transaction_id, 
                timestamp, 
                user_id, 
                merchant_id, 
                amount, 
                category, 
                country_code, 
                status 
            FROM '{parquet_path}'
            """
        )
        
        chunk_size = 100000
        cursor = conn.cursor()
        total_ingested = 0
        
        print("Ingesting records in chunks...")
        while True:
            chunk = res.fetchmany(chunk_size)
            if not chunk:
                break
                
            processed_chunk = []
            for row in chunk:
                tx_id, ts, u_id, m_id, amt, cat, cc, status = row
                # Convert timestamps (datetime objects) to ISO format string
                if hasattr(ts, "isoformat"):
                    ts = ts.isoformat()
                else:
                    ts = str(ts)
                processed_chunk.append((tx_id, ts, u_id, m_id, amt, cat, cc, status))
                
            cursor.execute("BEGIN TRANSACTION;")
            cursor.executemany(
                """
                INSERT OR IGNORE INTO transactions 
                (transaction_id, timestamp, user_id, merchant_id, amount, category, country_code, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, 
                processed_chunk
            )
            conn.commit()
            
            total_ingested += len(processed_chunk)
            print(f" - Ingested {total_ingested} records...")
            
        print("--------------------------------------------------")
        print("Ingestion completed successfully!")
        print(f"Total Rows Loaded: {total_ingested}")
        print(f"Time Taken: {time.time() - start_time:.2f} seconds")
        print("--------------------------------------------------")
        
    except Exception as e:
        print(f"CRITICAL ERROR during ingestion: {e}")
        try:
            conn.rollback()
        except:
            pass
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    setup_database()
