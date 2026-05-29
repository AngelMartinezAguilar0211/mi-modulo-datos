#!/usr/bin/env python3
import os
import sys
import json
import argparse
import uuid
from datetime import datetime, timezone, timedelta

CATEGORIES = {"Food", "Travel", "Electronics", "Health", "Entertainment", "Retail", "Transport", "Education", "Services", "Other"}
COUNTRIES = {"MX", "CO", "BR", "AR", "CL", "PE", "EC", "VE", "BO", "PY", "UY", "CR", "GT", "PA", "DO"}
STATUSES = {"completed", "failed", "pending"}

def validate_transaction(tx: dict) -> list[str]:
    """
    Validates a single transaction against specified business rules.
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
        
    # 5. Validation of timestamp
    ts_str = tx["timestamp"]
    try:
        # Replace Z with +00:00 to parse properly with fromisoformat on older versions
        if ts_str.endswith("Z"):
            clean_ts = ts_str[:-1] + "+00:00"
        else:
            clean_ts = ts_str
            
        dt = datetime.fromisoformat(clean_ts)
        
        # Ensure it is timezone aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
            
        now = datetime.now(timezone.utc)
        
        # Allow up to 1 hour of advance/lead time
        if dt > now + timedelta(hours=1):
            reasons.append("future_timestamp")
    except (ValueError, TypeError):
        reasons.append("future_timestamp") # unparseable counts as timestamp error

    # 6. Validation of transaction_id
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
    Validates normalized transactions.
    - Valid ones are collected in valid_list.
    - Rejected ones are written to quarantine/YYYY-MM-DD.jsonl.
    Returns (valid_list, rejected_list, error_counts).
    """
    if quarantine_dir is None:
        # Default to a quarantine folder
        quarantine_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quarantine")
        
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
                f.write(json.dumps(entry) + "\n")
                
    return valid_list, rejected_list, error_counts

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transformation, validation, and quarantine layer.")
    parser.add_argument("--file", type=str, default=None, help="Path to the JSON file with normalized transactions (if not using stdin).")
    parser.add_argument("--quarantine-dir", type=str, default=None, help="Directory for quarantined outputs.")
    
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
            
        valid, rejected, errors = transform_and_validate(data, quarantine_dir=args.quarantine_dir)
        
        print(json.dumps(valid, indent=4))

        print(f"Validation completed. Valid: {len(valid)} | Quarantined: {len(rejected)}", file=sys.stderr)
        print(f"Error metrics: {json.dumps(errors)}", file=sys.stderr)
        
    except Exception as e:
        print(f"Error in transformation: {e}", file=sys.stderr)
        sys.exit(1)
