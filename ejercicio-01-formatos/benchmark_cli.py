import argparse
import os
import json
import gc
from generate_data import generate_data
from storage_benchmark import benchmark_csv, benchmark_jsonl, benchmark_parquet

def main():
    parser = argparse.ArgumentParser(description="Run storage benchmark")
    parser.add_argument('--size', type=str, required=True, choices=['100k', '500k', '1m'])
    parser.add_argument('--formats', nargs='+', required=True, help="Formats to benchmark. E.g. csv jsonl parquet_uncompressed parquet_snappy parquet_gzip")
    args = parser.parse_args()
    
    print(f"Generating base dataset in memory for size {args.size}...")
    df = generate_data(args.size)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, '..', 'data')
    results_dir = os.path.join(script_dir, 'results')
    
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)
    
    results = []
    
    valid_formats = {
        'csv': lambda: benchmark_csv(df, os.path.join(data_dir, f'test_{args.size}.csv')),
        'jsonl': lambda: benchmark_jsonl(df, os.path.join(data_dir, f'test_{args.size}.jsonl')),
        'parquet_uncompressed': lambda: benchmark_parquet(df, os.path.join(data_dir, f'test_{args.size}_uncompressed.parquet'), compression=None),
        'parquet_snappy': lambda: benchmark_parquet(df, os.path.join(data_dir, f'test_{args.size}_snappy.parquet'), compression='snappy'),
        'parquet_gzip': lambda: benchmark_parquet(df, os.path.join(data_dir, f'test_{args.size}_gzip.parquet'), compression='gzip')
    }
    
    for fmt in args.formats:
        if fmt not in valid_formats:
            print(f"Warning: Format '{fmt}' not recognized. Skipping.")
            continue
            
        print(f"Running benchmark for {fmt}...")
        gc.collect()
        res = valid_formats[fmt]()
        results.append(res)
        
    output_path = os.path.join(results_dir, f'benchmark_{args.size}.json')
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=4)
        
    print(f"Benchmark complete. Results saved to {output_path}")

if __name__ == '__main__':
    main()
