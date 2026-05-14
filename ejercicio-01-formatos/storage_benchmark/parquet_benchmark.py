import time
import os
import tracemalloc
import pandas as pd
import gc
import statistics

def benchmark_parquet(df: pd.DataFrame, filepath: str, compression: str = None, iters: int = 5) -> dict:
    format_name = f"parquet_{compression}" if compression else "parquet_uncompressed"
    
    # Write benchmarks
    write_times = []
    for _ in range(iters):
        if os.path.exists(filepath):
            os.remove(filepath)
        gc.collect()
        
        start = time.perf_counter()
        df.to_parquet(filepath, engine='pyarrow', compression=compression, index=False)
        write_times.append(time.perf_counter() - start)
    
    avg_write_time = sum(write_times) / len(write_times)
    file_size_bytes = os.path.getsize(filepath)

    # Full read benchmarks
    read_times = []
    read_peaks = []
    for i in range(iters):
        gc.collect()
        tracemalloc.start()
        start = time.perf_counter()
        _ = pd.read_parquet(filepath, engine='pyarrow')
        elapsed = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        read_times.append(elapsed)
        read_peaks.append(peak)

    # Selective read benchmarks
    sel_read_times = []
    sel_read_peaks = []
    for i in range(iters):
        gc.collect()
        tracemalloc.start()
        start = time.perf_counter()
        _ = pd.read_parquet(filepath, engine='pyarrow', columns=['amount', 'category'])
        elapsed = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        sel_read_times.append(elapsed)
        sel_read_peaks.append(peak)

    # Use median of warm runs (discard first run)
    if iters > 1:
        full_read_time = statistics.median(read_times[1:])
        full_read_peak = statistics.median(read_peaks[1:])
        sel_read_time = statistics.median(sel_read_times[1:])
        sel_read_peak = statistics.median(sel_read_peaks[1:])
    else:
        full_read_time = read_times[0]
        full_read_peak = read_peaks[0]
        sel_read_time = sel_read_times[0]
        sel_read_peak = sel_read_peaks[0]

    return {
        'format': format_name,
        'write_time_avg': avg_write_time,
        'full_read_time': full_read_time,
        'selective_read_time': sel_read_time,
        'file_size_bytes': file_size_bytes,
        'peak_memory_bytes': full_read_peak,
        'selective_peak_memory_bytes': sel_read_peak
    }
