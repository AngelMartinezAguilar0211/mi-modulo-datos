import sys
import json
import argparse
from datetime import datetime

def normalize_timestamp(ts_str) -> str:
    """
    Normalizes the timestamp to ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ or similar).
    If it is not convertible, returns the original value or None to be filtered in transform.
    """
    if ts_str is None:
        return None
    
    ts_str = str(ts_str).strip()
    
    # Try parsing with various common formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d"
    ]
    
    # Handle the 'Z' suffix by replacing it with '+00:00' for older Python versions,
    # although Python 3.11+ handles native 'Z' in fromisoformat.
    if ts_str.endswith("Z"):
        clean_ts = ts_str[:-1] + "+00:00"
    else:
        clean_ts = ts_str
        
    try:
        # Try parsing using fromisoformat
        dt = datetime.fromisoformat(clean_ts)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        pass

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
        
    return ts_str  # If parsing fails, return the original for the validation layer to catch

def normalize_country_code(cc) -> str:
    """
    Normalizes country code to uppercase and strips whitespace.
    """
    if cc is None:
        return None
    return str(cc).strip().upper()

def normalize_amount(amount) -> float:
    """
    Normalizes the amount by converting to float and rounding to 2 decimal places.
    If it is not convertible, returns the original value.
    """
    if amount is None:
        return None
    try:
        val = float(amount)
        return round(val, 2)
    except (ValueError, TypeError):
        return amount

def extract_and_normalize(raw_transactions: list[dict]) -> list[dict]:
    """
    Takes a list of raw transactions and normalizes them field by field.
    """
    normalized_list = []
    for tx in raw_transactions:
        # Create a copy to avoid mutating the original
        norm_tx = tx.copy()
        
        # Basic structural normalizations
        if "timestamp" in norm_tx:
            norm_tx["timestamp"] = normalize_timestamp(norm_tx["timestamp"])
        if "country_code" in norm_tx:
            norm_tx["country_code"] = normalize_country_code(norm_tx["country_code"])
        if "amount" in norm_tx:
            norm_tx["amount"] = normalize_amount(norm_tx["amount"])
            
        # Ensure basic data types
        if "user_id" in norm_tx and norm_tx["user_id"] is not None:
            try:
                norm_tx["user_id"] = int(norm_tx["user_id"])
            except (ValueError, TypeError):
                pass
        if "merchant_id" in norm_tx and norm_tx["merchant_id"] is not None:
            try:
                norm_tx["merchant_id"] = int(norm_tx["merchant_id"])
            except (ValueError, TypeError):
                pass
                
        normalized_list.append(norm_tx)
        
    return normalized_list

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transaction extraction and normalization layer.")
    parser.add_argument("--file", type=str, default=None, help="Path to the JSON file with transactions (if not using stdin).")
    
    args = parser.parse_args()
    
    try:
        if args.file:
            with open(args.file, "r") as f:
                data = json.load(f)
        else:
            # Read from standard input (stdin)
            if sys.stdin.isatty():
                print("Error: No data provided via stdin or --file.", file=sys.stderr)
                parser.print_help()
                sys.exit(1)
            data = json.load(sys.stdin)
            
        if not isinstance(data, list):
            raise ValueError("The input JSON must be a list of transactions.")
            
        normalized = extract_and_normalize(data)
        print(json.dumps(normalized, indent=4))
        
    except Exception as e:
        print(f"Error in extraction: {e}", file=sys.stderr)
        sys.exit(1)
