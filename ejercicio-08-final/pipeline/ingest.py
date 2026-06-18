#!/usr/bin/env python3
"""
Pipeline orchestrator: chains extract → transform → load for CSV ingestion.
Can be invoked from the API endpoint or as a CLI tool.
"""
import os
import sys
import json
import argparse
import time
from datetime import datetime, timezone

from pipeline.extract_csv import extract_from_csv
from pipeline.transform import transform_and_validate
from pipeline.load import load_to_sqlite


def run_csv_pipeline(
    csv_path: str,
    db_path: str,
    quarantine_dir: str = None,
    results_dir: str = None
) -> dict:
    """
    Executes the entire ETL pipeline for a CSV file:
    1. Extracts and normalizes data from CSV (extract_csv)
    2. Validates business rules and quarantines failures (transform)
    3. Persists valid rows transactionally to SQLite (load)
    4. Saves metric JSON report under results/ (pipeline)

    Returns a metrics report dictionary.
    """
    start_time = time.perf_counter()
    run_timestamp = datetime.now(timezone.utc)
    run_id = run_timestamp.strftime("%Y%m%d_%H%M%S")

    # Resolve paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(base_dir)
    if quarantine_dir is None:
        quarantine_dir = os.path.join(project_dir, "quarantine")
    if results_dir is None:
        results_dir = os.path.join(project_dir, "results")

    os.makedirs(results_dir, exist_ok=True)

    # --- PHASE 1: Extraction from CSV ---
    raw_txs = extract_from_csv(csv_path)
    filas_extraidas = len(raw_txs)

    # --- PHASE 2: Business Validation ---
    valid_txs, rejected_txs, error_counts = transform_and_validate(
        raw_txs,
        quarantine_dir=quarantine_dir
    )
    filas_validas = len(valid_txs)
    filas_rechazadas = len(rejected_txs)

    # --- PHASE 3: Transactional SQLite Load ---
    filas_insertadas = 0
    filas_duplicadas = 0
    if filas_validas > 0:
        filas_insertadas, filas_duplicadas = load_to_sqlite(valid_txs, db_path)

    end_time = time.perf_counter()
    tiempo_total = end_time - start_time

    # --- PHASE 4: Execution Report ---
    report = {
        "run_id": run_id,
        "timestamp": run_timestamp.isoformat(),
        "source_file": os.path.basename(csv_path),
        "filas_extraidas": filas_extraidas,
        "filas_validas": filas_validas,
        "filas_rechazadas": filas_rechazadas,
        "filas_rechazadas_por_tipo_de_error": error_counts,
        "filas_insertadas": filas_insertadas,
        "filas_duplicadas": filas_duplicadas,
        "tiempo_total": round(tiempo_total, 6)
    }

    report_file_path = os.path.join(results_dir, f"run_{run_id}.json")
    with open(report_file_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4)

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CSV pipeline orchestrator (ETL).")
    parser.add_argument("--csv", type=str, required=True, help="Path to the CSV file to ingest.")
    parser.add_argument("--db", type=str, required=True, help="Path to the SQLite database file.")
    parser.add_argument("--quarantine", type=str, default=None, help="Output directory for quarantined records.")
    parser.add_argument("--results", type=str, default=None, help="Output directory for JSON execution reports.")

    args = parser.parse_args()

    try:
        report = run_csv_pipeline(
            csv_path=args.csv,
            db_path=args.db,
            quarantine_dir=args.quarantine,
            results_dir=args.results
        )

        print(json.dumps(report, indent=4))

    except Exception as e:
        print(f"\nPipeline execution failed: {e}\n", file=sys.stderr)
        sys.exit(1)
