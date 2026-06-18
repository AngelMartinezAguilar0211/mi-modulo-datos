import sqlite3
import os


def load_to_sqlite(valid_transactions: list[dict], db_path: str) -> tuple[int, int]:
    """
    Loads valid transactions into SQLite in a transactional and idempotent manner.
    Uses 'INSERT OR IGNORE' to prevent duplicate records.
    If any failure occurs, performs a complete rollback of the entire batch.

    Returns (inserted_rows, duplicate_rows).
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"SQLite database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    # Batch write performance optimizations
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")

    inserted_count = 0
    duplicate_count = 0

    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION;")

        for tx in valid_transactions:
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

            # rowcount > 0 indicates the row was successfully inserted.
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
