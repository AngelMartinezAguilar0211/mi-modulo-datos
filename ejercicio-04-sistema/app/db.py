import sqlite3
import duckdb
import os
from pathlib import Path

class DatabaseManager:
    def __init__(self):
        self.sqlite_conn = None
        self.duckdb_conn = None
        self.sqlite_path = None
        self.parquet_path = None

    def init_db(self, sqlite_path: str, parquet_path: str):
        self.sqlite_path = sqlite_path
        self.parquet_path = parquet_path

        # 1. Initialize SQLite connection (optimized for OLTP)
        # check_same_thread=False is required for concurrent FastAPI request handling
        self.sqlite_conn = sqlite3.connect(sqlite_path, check_same_thread=False)
        self.sqlite_conn.row_factory = sqlite3.Row
        
        # SQLite performance optimizations
        self.sqlite_conn.execute("PRAGMA journal_mode=WAL;")
        self.sqlite_conn.execute("PRAGMA synchronous=NORMAL;")
        self.sqlite_conn.execute("PRAGMA cache_size=10000;")
        
        # 2. Initialize DuckDB connection (optimized for OLAP)
        # The connection uses an in-memory database and points to the Parquet file via a VIEW
        self.duckdb_conn = duckdb.connect(database=":memory:", read_only=False)
        
        if not os.path.exists(parquet_path):
            raise FileNotFoundError(f"Parquet dataset not found at {parquet_path}")
            
        self.duckdb_conn.execute(f"CREATE OR REPLACE VIEW transactions_view AS SELECT * FROM '{parquet_path}';")
        
        print("Database connections initialized successfully.")
        print(f"SQLite DB: {sqlite_path}")
        print(f"DuckDB Parquet: {parquet_path}")

    def close(self):
        if self.sqlite_conn:
            self.sqlite_conn.close()
            print("SQLite connection closed.")
        if self.duckdb_conn:
            self.duckdb_conn.close()
            print("DuckDB connection closed.")

    def get_sqlite_conn(self):
        if not self.sqlite_conn:
            raise RuntimeError("SQLite database is not initialized.")
        return self.sqlite_conn

    def get_duckdb_cursor(self):
        if not self.duckdb_conn:
            raise RuntimeError("DuckDB database is not initialized.")
        # DuckDB requires a .cursor() clone per thread to be completely thread-safe
        return self.duckdb_conn.cursor()

db_manager = DatabaseManager()
