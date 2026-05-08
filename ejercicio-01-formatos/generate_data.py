import argparse
import pandas as pd
import numpy as np
import uuid
from datetime import datetime, timedelta
import os

def generate_data(size_str: str) -> pd.DataFrame:
    size_map = {'100k': 100_000, '500k': 500_000, '1m': 1_000_000}
    if size_str not in size_map:
        raise ValueError("Size must be 100k, 500k or 1m")
    
    n = size_map[size_str]
    print(f"Generating {n} rows of data...")
    
    # Pre-generate values using numpy for speed
    transaction_ids = [str(uuid.uuid4()) for _ in range(n)]
    
    now = datetime.now()
    one_year_ago = now - timedelta(days=365)
    start_ts = one_year_ago.timestamp()
    end_ts = now.timestamp()
    random_ts = np.random.uniform(start_ts, end_ts, n)
    timestamps = pd.to_datetime(random_ts, unit='s')
    
    user_ids = np.random.randint(1, 50001, n)
    merchant_ids = np.random.randint(1, 10001, n)
    amounts = np.round(np.random.uniform(0.01, 5000.00, n), 2)
    
    categories = ['Food', 'Travel', 'Electronics', 'Health', 'Entertainment', 'Retail', 'Transport', 'Education', 'Services', 'Other']
    categories_col = np.random.choice(categories, n)
    
    country_codes = ['MX', 'CO', 'BR', 'AR', 'CL', 'PE', 'EC', 'VE', 'BO', 'PY', 'UY', 'CR', 'GT', 'PA', 'DO']
    countries_col = np.random.choice(country_codes, n)
    
    statuses = ['completed', 'failed', 'pending']
    probabilities = [0.85, 0.10, 0.05]
    statuses_col = np.random.choice(statuses, n, p=probabilities)
    
    df = pd.DataFrame({
        'transaction_id': transaction_ids,
        'timestamp': timestamps,
        'user_id': user_ids,
        'merchant_id': merchant_ids,
        'amount': amounts,
        'category': categories_col,
        'country_code': countries_col,
        'status': statuses_col
    })
    
    return df

def main():
    parser = argparse.ArgumentParser(description="Generate transaction dataset")
    parser.add_argument('--size', type=str, required=True, choices=['100k', '500k', '1m'], help="Size of the dataset")
    args = parser.parse_args()
    
    df = generate_data(args.size)
    
    # Path to the data directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, '..', 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    output_path = os.path.join(data_dir, f'dataset_{args.size}.csv')
    print(f"Saving to {output_path}...")
    df.to_csv(output_path, index=False)
    print("Done!")

if __name__ == '__main__':
    main()
