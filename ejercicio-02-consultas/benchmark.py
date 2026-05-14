import os
import json
import time
import tracemalloc
import argparse
import gc
import statistics
import pandas as pd
from pandas.testing import assert_frame_equal

# Import engines
from engines import pandas_engine, polars_engine, duckdb_engine

DATA_PATH = os.path.join("..", "data", "test_1m_snappy.parquet")

def normalize_df(df):
    """Normalize dataframe for comparison."""
    if df is None:
        return None
    
    # Sort columns
    df = df.reindex(sorted(df.columns), axis=1)
    
    # Sort values to ensure row order consistency
    df = df.sort_values(by=list(df.columns)).reset_index(drop=True)
    
    # Ensure consistent dtypes for common columns (e.g. counts as int64)
    for col in df.columns:
        col_lower = col.lower()
        # Avoid matching 'country_code'
        if ("count" in col_lower or "failed_count" in col_lower) and "country" not in col_lower:
            try:
                df[col] = df[col].astype("int64")
            except:
                pass
        if any(x in col_lower for x in ["amount", "sum", "mean", "avg", "min", "max"]):
            try:
                df[col] = df[col].astype("float64").round(4)
            except:
                pass
        if "date" in col_lower:
            try:
                df[col] = pd.to_datetime(df[col])
            except:
                pass
            
    return df

def validate_equivalence(results):
    """Validate that results from all 3 engines are equivalent."""
    engines = list(results.keys())
    if len(engines) < 2:
        return True, "Only one engine run, nothing to compare."
    
    base_engine = engines[0]
    base_df = normalize_df(results[base_engine])
    
    for other_engine in engines[1:]:
        other_df = normalize_df(results[other_engine])
        try:
            assert_frame_equal(base_df, other_df, check_dtype=False, atol=1e-3)
        except Exception as e:
            return False, f"Mismatch between {base_engine} and {other_engine}: {str(e)}"
    
    return True, "All engines equivalent."

def run_benchmark():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results/", help="Output directory for results")
    parser.add_argument("--iters", type=int, default=5, help="Number of iterations per query")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    engines = {
        "pandas": pandas_engine,
        "polars": polars_engine,
        "duckdb": duckdb_engine
    }

    results_summary = []
    
    # Get absolute path for Parquet
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parquet_path = os.path.join(os.path.dirname(script_dir), "data", "test_1m_snappy.parquet")

    if not os.path.exists(parquet_path):
        print(f"Error: {parquet_path} not found.")
        return

    print(f"Starting rigorous benchmark ({args.iters} iterations)...")
    print("Note: Peak RAM might be underreported for native engines (DuckDB/Polars) due to tracemalloc limitations.\n")

    for q_num in range(1, 9):
        q_id = f"Q{q_num}"
        print(f"Benchmarking {q_id}...")
        
        q_results = {}
        q_metrics = {}

        for name, engine in engines.items():
            func = getattr(engine, q_id.lower())
            
            times = []
            peaks = []
            last_df = None
            
            for i in range(args.iters):
                gc.collect()
                tracemalloc.start()
                start_time = time.perf_counter()
                
                try:
                    # Execute query
                    res_df = func(parquet_path)
                    
                    end_time = time.perf_counter()
                    current, peak = tracemalloc.get_traced_memory()
                    tracemalloc.stop()
                    
                    execution_time = end_time - start_time
                    peak_ram_mb = peak / (1024 * 1024)
                    
                    times.append(execution_time)
                    peaks.append(peak_ram_mb)
                    last_df = res_df
                    
                except Exception as e:
                    tracemalloc.stop()
                    print(f"  {name} iteration {i+1} FAILED: {e}")
                    q_metrics[name] = {"error": str(e)}
                    break
            
            if name not in q_metrics or "error" not in q_metrics[name]:
                # Calculate metrics
                # Discard first run (cold start) if more than 1 iteration
                if len(times) > 1:
                    warm_times = times[1:]
                    warm_peaks = peaks[1:]
                    cold_time = times[0]
                else:
                    warm_times = times
                    warm_peaks = peaks
                    cold_time = times[0]
                
                median_time = statistics.median(warm_times)
                median_peak = statistics.median(warm_peaks)
                
                q_results[name] = last_df
                q_metrics[name] = {
                    "time_s": median_time,
                    "ram_mb": median_peak,
                    "cold_time_s": cold_time,
                    "all_times": times
                }
                print(f"  {name}: median {median_time:.4f}s (cold: {cold_time:.4f}s), peak {median_peak:.2f}MB")

        # Validate
        valid, msg = validate_equivalence(q_results)
        print(f"  Validation: {msg}")

        results_summary.append({
            "query": q_id,
            "metrics": q_metrics,
            "validation": {
                "success": valid,
                "message": msg
            }
        })

    # Capture EXPLAIN ANALYZE for DuckDB
    print("Capturing EXPLAIN ANALYZE for DuckDB (Q3, Q5, Q6)...")
    explains = {}
    for q_id in ["Q3", "Q5", "Q6"]:
        explains[q_id] = duckdb_engine.get_explain_analyze(q_id, parquet_path)

    output_file = os.path.join(args.output, "benchmark_results.json")
    with open(output_file, "w") as f:
        json.dump({
            "results": results_summary,
            "explains": explains
        }, f, indent=4)

    print(f"\nDone! Results saved to {output_file}")

if __name__ == "__main__":
    run_benchmark()
