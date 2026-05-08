import time
import os
import tracemalloc
import pandas as pd
import gc

def benchmark_csv(df: pd.DataFrame, filepath: str) -> dict:
    write_times = []
    for _ in range(3):
        start = time.perf_counter()
        df.to_csv(filepath, index=False)
        write_times.append(time.perf_counter() - start)
    avg_write_time = sum(write_times) / len(write_times)

    file_size_bytes = os.path.getsize(filepath)

    gc.collect()
    tracemalloc.start()
    start = time.perf_counter()
    _ = pd.read_csv(filepath)
    full_read_time = time.perf_counter() - start
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    start = time.perf_counter()
    _ = pd.read_csv(filepath, usecols=['amount', 'category'])
    selective_read_time = time.perf_counter() - start

    return {
        'format': 'csv',
        'write_time_avg': avg_write_time,
        'full_read_time': full_read_time,
        'selective_read_time': selective_read_time,
        'file_size_bytes': file_size_bytes,
        'peak_memory_bytes': peak_memory
    }
