import sqlite3
import duckdb
import os
import sys
import logging
from pathlib import Path

# Get logger configured in main app
logger = logging.getLogger("api_db")

class DatabaseManager:
    def __init__(self):
        self.sqlite_conn = None
        self.duckdb_conn = None
        self.sqlite_path = None
        self.parquet_path = None

    def init_db(self, sqlite_path: str, parquet_path: str):
        self.sqlite_path = sqlite_path
        self.parquet_path = parquet_path

        # Validate that the SQLite database file path is provided and exists
        if not sqlite_path:
            logger.error("Environment variable SQLITE_DB_PATH is not set.")
            sys.exit("CRITICAL: Environment variable SQLITE_DB_PATH is not set.")
            
        if not os.path.exists(sqlite_path):
            logger.error(f"SQLite database file not found at: {sqlite_path}")
            sys.exit(f"CRITICAL: SQLite database file not found at: {sqlite_path}. Make sure the setup container runs successfully first.")

        # Validate that the Parquet dataset file exists
        if not parquet_path:
            logger.error("Environment variable PARQUET_FILE_PATH is not set.")
            sys.exit("CRITICAL: Environment variable PARQUET_FILE_PATH is not set.")
            
        if not os.path.exists(parquet_path):
            logger.error(f"Parquet dataset not found at: {parquet_path}")
            sys.exit(f"CRITICAL: Parquet dataset not found at: {parquet_path}")

        # 1. Initialize SQLite connection (optimized for OLTP)
        # check_same_thread=False is required for concurrent request handling in FastAPI
        try:
            self.sqlite_conn = sqlite3.connect(sqlite_path, check_same_thread=False)
            self.sqlite_conn.row_factory = sqlite3.Row
            
            # SQLite performance configurations
            self.sqlite_conn.execute("PRAGMA journal_mode=WAL;")
            self.sqlite_conn.execute("PRAGMA synchronous=NORMAL;")
            self.sqlite_conn.execute("PRAGMA cache_size=10000;")
            logger.info("SQLite connection initialized successfully with WAL mode.")
        except Exception as e:
            logger.error(f"Failed to connect to SQLite: {e}")
            sys.exit(f"CRITICAL: Failed to connect to SQLite: {e}")

        # 2. Initialize DuckDB connection (optimized for OLAP)
        try:
            self.duckdb_conn = duckdb.connect(database=":memory:", read_only=False)
            self.duckdb_conn.execute(f"CREATE OR REPLACE VIEW transactions_view AS SELECT * FROM '{parquet_path}';")
            logger.info("DuckDB in-memory OLAP view initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize DuckDB view: {e}")
            sys.exit(f"CRITICAL: Failed to initialize DuckDB view: {e}")

        logger.info(f"Database Manager successfully loaded: SQLite={sqlite_path}, Parquet={parquet_path}")

    def close(self):
        if self.sqlite_conn:
            try:
                self.sqlite_conn.close()
                logger.info("SQLite connection closed.")
            except Exception as e:
                logger.error(f"Error closing SQLite: {e}")
        if self.duckdb_conn:
            try:
                self.duckdb_conn.close()
                logger.info("DuckDB connection closed.")
            except Exception as e:
                logger.error(f"Error closing DuckDB: {e}")

    def get_sqlite_conn(self):
        if not self.sqlite_conn:
            raise RuntimeError("SQLite database is not initialized.")
        return self.sqlite_conn

    def get_duckdb_cursor(self):
        if not self.duckdb_conn:
            raise RuntimeError("DuckDB database is not initialized.")
        # Returns a clone cursor of the connection to ensure safe concurrent thread usage
        return self.duckdb_conn.cursor()

db_manager = DatabaseManager()
