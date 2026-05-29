import argparse
import json
import random
import uuid
import sys
from datetime import datetime, timedelta, timezone

CATEGORIES = ["Food", "Travel", "Electronics", "Health", "Entertainment", "Retail", "Transport", "Education", "Services", "Other"]
COUNTRIES = ["MX", "CO", "BR", "AR", "CL", "PE", "EC", "VE", "BO", "PY", "UY", "CR", "GT", "PA", "DO"]
STATUSES = ["completed", "failed", "pending"]

def generate_batch(batch_size: int = None, error_rate: float = 0.1) -> list[dict]:
    """
    Generates a batch of transactions using the specified schema.
    Injects deliberate errors based on the `error_rate`.
    """
    if batch_size is None:
        batch_size = random.randint(100, 1000)
    
    batch = []
    now = datetime.now(timezone.utc)
    
    for _ in range(batch_size):
        # 1. Generate fully valid base transaction
        tx_id = str(uuid.uuid4())
        
        # Timestamp in last 15 days
        delta_past = timedelta(
            days=random.randint(0, 15),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59)
        )
        ts = (now - delta_past).isoformat()
        
        user_id = random.randint(1, 50000)
        merchant_id = random.randint(1, 10000)
        
        # Amount with up to 4 decimals
        amount = round(random.uniform(0.01, 5000.00), 4)
        
        # Categories and countries
        category = random.choice(CATEGORIES)
        country_code = random.choice(COUNTRIES)
        
        # Small percentage of country codes in lowercase
        if random.random() < 0.3:
            country_code = country_code.lower()
            
        status = random.choice(STATUSES)
        
        tx = {
            "transaction_id": tx_id,
            "timestamp": ts,
            "user_id": user_id,
            "merchant_id": merchant_id,
            "amount": amount,
            "category": category,
            "country_code": country_code,
            "status": status
        }
        
        # 2. Inject deliberate errors if random() < error_rate
        if random.random() < error_rate:
            error_type = random.randint(0, 5)
            
            if error_type == 0:
                # Invalid amounts: negative, zero, or extremely high
                tx["amount"] = random.choice([-50.0, 0.0, 7500.0])
            elif error_type == 1:
                # Invalid categories
                tx["category"] = random.choice(["Illegal", "Weapons", "Gambling", "InvalidCategory"])
            elif error_type == 2:
                # Invalid countries
                tx["country_code"] = random.choice(["US", "FR", "JP", "XX"])
            elif error_type == 3:
                # Future timestamps (more than 1 hour in advance)
                future_delta = timedelta(hours=random.randint(2, 24))
                tx["timestamp"] = (now + future_delta).isoformat()
            elif error_type == 4:
                # Malformed UUIDs
                tx["transaction_id"] = random.choice(["not-a-uuid", "123-abc-uuid", "g1a2b3c4-d5e6-f7g8-h9i0-j1k2l3m4n5o6"])
            elif error_type == 5:
                # Null/empty values in mandatory fields
                nullify_field = random.choice(list(tx.keys()))
                tx[nullify_field] = None
                
        batch.append(tx)
        
    return batch

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transaction source simulator with error injection.")
    parser.add_argument("--batch-size", type=int, default=None, help="Number of transactions to generate (100 - 1000).")
    parser.add_argument("--error-rate", type=float, default=0.1, help="Deliberate error rate (0.0 to 1.0).")
    
    args = parser.parse_args()
    
    try:
        transactions = generate_batch(batch_size=args.batch_size, error_rate=args.error_rate)
        print(json.dumps(transactions, indent=4))
    except Exception as e:
        print(f"Error in simulation: {e}", file=sys.stderr)
        sys.exit(1)
