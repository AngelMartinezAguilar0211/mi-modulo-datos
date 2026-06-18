import csv
import os
import sys
from datetime import datetime


def normalize_timestamp(ts_str) -> str:
    """
    Normalizes the timestamp to ISO 8601 format.
    If parsing fails, returns the original value for the validation layer to catch.
    """
    if ts_str is None:
        return None

    ts_str = str(ts_str).strip()

    # Handle the 'Z' suffix for Python compatibility
    if ts_str.endswith("Z"):
        clean_ts = ts_str[:-1] + "+00:00"
    else:
        clean_ts = ts_str

    try:
        dt = datetime.fromisoformat(clean_ts)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        pass

    # Try common formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d"
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(ts_str, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue

    # Try parsing as a Unix timestamp (numeric)
    try:
        val = float(ts_str)
        if val > 946684800:
            dt = datetime.fromtimestamp(val)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        pass

    return ts_str


def normalize_country_code(cc) -> str:
    """Normalizes country code to uppercase and strips whitespace."""
    if cc is None:
        return None
    return str(cc).strip().upper()


def normalize_amount(amount) -> float:
    """Normalizes the amount by converting to float and rounding to 2 decimal places."""
    if amount is None:
        return None
    try:
        val = float(amount)
        return round(val, 2)
    except (ValueError, TypeError):
        return amount


def extract_from_csv(csv_path: str) -> list[dict]:
    """
    Reads a CSV file and returns a list of normalized transaction dictionaries.
    Expected CSV columns: transaction_id, timestamp, user_id, merchant_id,
                          amount, category, country_code, status
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    transactions = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Normalize each field
            tx = {}
            tx["transaction_id"] = row.get("transaction_id", "").strip() if row.get("transaction_id") else None
            tx["timestamp"] = normalize_timestamp(row.get("timestamp"))
            tx["category"] = row.get("category", "").strip() if row.get("category") else None
            tx["country_code"] = normalize_country_code(row.get("country_code"))
            tx["status"] = row.get("status", "").strip() if row.get("status") else None
            tx["amount"] = normalize_amount(row.get("amount"))

            # Normalize integer fields
            try:
                tx["user_id"] = int(row.get("user_id", 0))
            except (ValueError, TypeError):
                tx["user_id"] = row.get("user_id")

            try:
                tx["merchant_id"] = int(row.get("merchant_id", 0))
            except (ValueError, TypeError):
                tx["merchant_id"] = row.get("merchant_id")

            transactions.append(tx)

    return transactions
