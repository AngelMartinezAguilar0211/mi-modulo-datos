import sqlite3
import os
import sys
import json
import argparse

def init_database(db_path: str):
    """
    Initializes the database with the 'transactions' table and optimized B-tree indices.
    Utilizes the Covering Index (idx_country_user) based on E03 feedback.
    """
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
        
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        
        # Create table if it does not exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
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
        
        # Optimized index for P2, P3, and P4
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_timestamp ON transactions (user_id, timestamp DESC);")
        
        # Cover index for P5
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_country_user ON transactions (country_code, user_id);")
        
        conn.commit()
    finally:
        conn.close()

def load_to_sqlite(valid_transactions: list[dict], db_path: str, force_error_at: int = None) -> tuple[int, int]:
    """
    Loads valid transactions into SQLite in a transactional and idempotent manner.
    Uses 'INSERT OR IGNORE' to prevent duplicate records.
    If any failure occurs, performs a complete rollback of the entire batch.
    
    force_error_at: Test parameter to force an exception at the specified loop index.
    Returns (inserted_rows, duplicate_rows).
    """
    # Ensure database is initialized
    init_database(db_path)
    
    conn = sqlite3.connect(db_path)
    # Batch write performance optimizations
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    
    inserted_count = 0
    duplicate_count = 0
    
    try:
        cursor = conn.cursor()

        cursor.execute("BEGIN TRANSACTION;")
        
        for i, tx in enumerate(valid_transactions):
            # Error simulation for atomicity test
            if force_error_at is not None and i == force_error_at:
                raise RuntimeError("Simulated database failure for transactional testing.")
                
            cursor.execute(
                """
                INSERT OR IGNORE INTO transactions 
                (transaction_id, timestamp, user_id, merchant_id, amount, category, country_code, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tx["transaction_id"],
                    tx["timestamp"],
                    tx["user_id"],
                    tx["merchant_id"],
                    tx["amount"],
                    tx["category"],
                    tx["country_code"],
                    tx["status"]
                )
            )
            
            # rowcount > 0 indicates that the row was successfully inserted.
            # If the transaction_id already existed, rowcount will be 0 due to IGNORE.
            if cursor.rowcount > 0:
                inserted_count += 1
            else:
                duplicate_count += 1
                
        # Commit transaction on success
        conn.commit()
        
    except Exception as e:
        # Roll back all changes if any failure occurs
        conn.rollback()
        raise e
    finally:
        conn.close()
        
    return inserted_count, duplicate_count

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transactional loader into SQLite.")
    parser.add_argument("--file", type=str, default=None, help="Path to the JSON file with valid transactions (if not using stdin).")
    parser.add_argument("--db", type=str, required=True, help="Path to the SQLite database file.")
    
    args = parser.parse_args()
    
    try:
        if args.file:
            with open(args.file, "r") as f:
                data = json.load(f)
        else:
            if sys.stdin.isatty():
                print("Error: No data provided via stdin or --file.", file=sys.stderr)
                parser.print_help()
                sys.exit(1)
            data = json.load(sys.stdin)
            
        if not isinstance(data, list):
            raise ValueError("The input JSON must be a list of transactions.")
            
        inserted, duplicates = load_to_sqlite(data, args.db)
        print(json.dumps({
            "filas_insertadas": inserted,
            "filas_duplicadas": duplicates
        }, indent=4))
        
    except Exception as e:
        print(f"Error in loading: {e}", file=sys.stderr)
        sys.exit(1)
