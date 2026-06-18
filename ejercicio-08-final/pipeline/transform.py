import os
import json
import uuid
from datetime import datetime, timezone, timedelta

# Domain constants (same whitelist as app/models.py)
CATEGORIES = {"Food", "Travel", "Electronics", "Health", "Entertainment", "Retail", "Transport", "Education", "Services", "Other"}
COUNTRIES = {"MX", "CO", "BR", "AR", "CL", "PE", "EC", "VE", "BO", "PY", "UY", "CR", "GT", "PA", "DO"}
STATUSES = {"completed", "failed", "pending"}


def validate_transaction(tx: dict) -> list[str]:
    """
    Validates a single transaction against business rules.
    Returns a list of rejection reasons (empty if the transaction is valid).
    """
    reasons = []

    # 1. Check required fields
    required_fields = ["transaction_id", "timestamp", "user_id", "merchant_id", "amount", "category", "country_code", "status"]
    missing = [f for f in required_fields if f not in tx or tx[f] is None]
    if missing:
        reasons.append("missing_fields")
        # If crucial fields are missing, skip further validations to avoid exceptions
        return reasons

    # 2. Validation of amount (0.01 - 5000.00)
    try:
        amount = float(tx["amount"])
        if amount < 0.01 or amount > 5000.00:
            reasons.append("amount_out_of_range")
    except (ValueError, TypeError):
        reasons.append("amount_out_of_range")

    # 3. Validation of category
    if tx["category"] not in CATEGORIES:
        reasons.append("invalid_category")

    # 4. Validation of country_code
    if tx["country_code"] not in COUNTRIES:
        reasons.append("invalid_country")

    # 5. Validation of timestamp (reject future timestamps beyond 1 hour)
    ts_str = tx["timestamp"]
    try:
        if ts_str.endswith("Z"):
            clean_ts = ts_str[:-1] + "+00:00"
        else:
            clean_ts = ts_str

        dt = datetime.fromisoformat(clean_ts)

        # Ensure it is timezone aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)

        if dt > now + timedelta(hours=1):
            reasons.append("future_timestamp")
    except (ValueError, TypeError):
        reasons.append("future_timestamp")

    # 6. Validation of transaction_id (must be valid UUID4)
    tx_id = tx["transaction_id"]
    try:
        val = uuid.UUID(str(tx_id))
        if val.version != 4:
            reasons.append("invalid_uuid")
    except (ValueError, TypeError, AttributeError):
        reasons.append("invalid_uuid")

    return reasons


def transform_and_validate(normalized_transactions: list[dict], quarantine_dir: str = None) -> tuple[list[dict], list[dict], dict]:
    """
    Validates normalized transactions against business rules.
    - Valid transactions are collected in valid_list.
    - Rejected transactions are written to quarantine/YYYY-MM-DD.jsonl with reasons.
    Returns (valid_list, rejected_list, error_counts).
    """
    if quarantine_dir is None:
        quarantine_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "quarantine")

    os.makedirs(quarantine_dir, exist_ok=True)

    valid_list = []
    rejected_list = []

    # Initialize error type metrics
    error_counts = {
        "amount_out_of_range": 0,
        "invalid_category": 0,
        "invalid_country": 0,
        "future_timestamp": 0,
        "invalid_uuid": 0,
        "missing_fields": 0
    }

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    quarantine_file_path = os.path.join(quarantine_dir, f"{today_str}.jsonl")

    rejected_to_write = []

    for tx in normalized_transactions:
        reasons = validate_transaction(tx)

        if not reasons:
            valid_list.append(tx)
        else:
            rejected_list.append(tx)
            for r in reasons:
                if r in error_counts:
                    error_counts[r] += 1

            quarantine_entry = {
                "transaction": tx,
                "rejection_reasons": reasons,
                "quarantined_at": datetime.now(timezone.utc).isoformat()
            }
            rejected_to_write.append(quarantine_entry)

    if rejected_to_write:
        with open(quarantine_file_path, "a", encoding="utf-8") as f:
            for entry in rejected_to_write:
                f.write(json.dumps(entry, default=str) + "\n")

    return valid_list, rejected_list, error_counts
