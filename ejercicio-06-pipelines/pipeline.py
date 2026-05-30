#!/usr/bin/env python3
import os
import sys
import json
import argparse
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_source import generate_batch
from extract import extract_and_normalize
from transform import transform_and_validate
from load import load_to_sqlite

# ANSI color codes for console output
CYAN = "\033[1;36m"
GREEN = "\033[1;32m"
YELLOW = "\033[1;33m"
RED = "\033[1;31m"
RESET = "\033[0m"
BOLD = "\033[1m"
GRAY = "\033[90m"

def run_pipeline(
    batch_size: int = None,
    error_rate: float = 0.1,
    db_path: str = None,
    quarantine_dir: str = None,
    results_dir: str = None
) -> dict:
    """
    Executes the entire ETL pipeline:
    1. Generates simulated batch (data_source)
    2. Normalizes data formats (extract)
    3. Validates business rules and quarantines failures (transform)
    4. Persists transactionally to SQLite (load)
    5. Saves metric JSON reports under results/ (pipeline)
    """
    start_time = time.perf_counter()
    run_timestamp = datetime.now(timezone.utc)
    run_id = run_timestamp.strftime("%Y%m%d_%H%M%S")
    
    # Resolve paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if db_path is None:
        db_path = os.path.join(base_dir, "..", "data", "transactions.db")
    if quarantine_dir is None:
        quarantine_dir = os.path.join(base_dir, "quarantine")
    if results_dir is None:
        results_dir = os.path.join(base_dir, "results")
        
    os.makedirs(results_dir, exist_ok=True)
    
    # --- PHASE 1: Extraction ---
    raw_txs = generate_batch(batch_size=batch_size, error_rate=error_rate)
    filas_extraidas = len(raw_txs)
    
    # --- PHASE 2: Normalization ---
    normalized_txs = extract_and_normalize(raw_txs)
    
    # --- PHASE 3: Transformation and Business Validation ---
    valid_txs, rejected_txs, error_counts = transform_and_validate(
        normalized_txs, 
        quarantine_dir=quarantine_dir
    )
    filas_validas = len(valid_txs)
    filas_rechazadas = len(rejected_txs)
    
    # --- PHASE 4: Transactional SQLite Load ---
    filas_insertadas = 0
    filas_duplicadas = 0
    if filas_validas > 0:
        filas_insertadas, filas_duplicadas = load_to_sqlite(valid_txs, db_path)
        
    end_time = time.perf_counter()
    tiempo_total = end_time - start_time
    
    # --- PHASE 5: Execution Report ---
    report = {
        "run_id": run_id,
        "timestamp": run_timestamp.isoformat(),
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

def print_dashboard(report: dict, db_path: str, quarantine_dir: str):
    """
    Prints an aesthetic and visually premium execution summary dashboard in the console.
    """
    print("\n" + CYAN + "="*65 + RESET)
    print(CYAN + BOLD + " PIPELINE DE INGESTA TRANSACCIONAL - REPORTE EJECUTIVO " + RESET)
    print(CYAN + "="*65 + RESET)
    
    print(f" {BOLD}ID de Ejecución:{RESET} {report['run_id']}")
    print(f" {BOLD}Fecha (UTC):{RESET}    {report['timestamp']}")
    print(f" {BOLD}Base de Datos:{RESET}   {os.path.abspath(db_path)}")
    print(f" {BOLD}Cuarentena:{RESET}      {os.path.abspath(quarantine_dir)}")
    print(GRAY + "-"*65 + RESET)
    
    # Volumetric metrics
    print(f" {CYAN}{BOLD}[+] VOLUMETRÍA DE DATOS{RESET}")
    print(f"   Filas Extraídas (Raw):     {BOLD}{report['filas_extraidas']}{RESET}")
    print(f"   Filas Válidas (Negocio):   {GREEN}{report['filas_validas']}{RESET}")
    
    if report['filas_rechazadas'] > 0:
        print(f"   Filas Rechazadas (Quarantine): {RED}{report['filas_rechazadas']}{RESET}")
    else:
        print(f"   Filas Rechazadas (Quarantine): {GREEN}0{RESET}")
        
    print(GRAY + "-"*65 + RESET)
    
    # Anomalies breakdown
    print(f" {YELLOW}{BOLD}[!] DESGLOSE DE ANOMALÍAS ENCONTRADAS{RESET}")
    err_counts = report["filas_rechazadas_por_tipo_de_error"]
    has_errors = False
    
    for err_type, count in err_counts.items():
        if count > 0:
            has_errors = True
            clean_name = err_type.replace("_", " ").title()
            print(f"   • {clean_name:<30} {RED}{count:>6} filas{RESET}")
            
    if not has_errors:
        print(f"   {GREEN}No se detectaron anomalías en este lote de transacciones. 🎉{RESET}")
        
    print(GRAY + "-"*65 + RESET)
    
    # SQLite persistence results
    print(f" {GREEN}{BOLD}PERSISTENCIA EN SQLite (IDEMPOTENTE){RESET}")
    print(f"   Nuevas Filas Insertadas:   {GREEN}{BOLD}{report['filas_insertadas']}{RESET}")
    print(f"   Filas Duplicadas Omitidas: {YELLOW}{report['filas_duplicadas']}{RESET}")
    
    print(GRAY + "-"*65 + RESET)
    
    # Performance metrics
    print(f" {CYAN}{BOLD}MÉTRICAS DE RENDIMIENTO{RESET}")
    print(f"   Tiempo Total de Corrida:   {BOLD}{report['tiempo_total']:.4f} segundos{RESET}")
    
    if report['tiempo_total'] > 0:
        rate = report['filas_extraidas'] / report['tiempo_total']
        print(f"   Tasa de Procesamiento:      {BOLD}{rate:.2f} filas/segundo{RESET}")
        
    print(CYAN + "="*65 + RESET + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Global pipeline (ETL) orchestrator.")
    parser.add_argument("--batch-size", type=int, default=None, help="Number of transactions to generate (100 - 1000).")
    parser.add_argument("--error-rate", type=float, default=0.1, help="Simulated error rate (0.0 to 1.0).")
    parser.add_argument("--db", type=str, default=None, help="Path to the SQLite database file.")
    parser.add_argument("--quarantine", type=str, default=None, help="Output directory for quarantined log files.")
    parser.add_argument("--results", type=str, default=None, help="Output directory for JSON performance reports.")
    
    args = parser.parse_args()
    
    try:
        # Run pipeline
        report = run_pipeline(
            batch_size=args.batch_size,
            error_rate=args.error_rate,
            db_path=args.db,
            quarantine_dir=args.quarantine,
            results_dir=args.results
        )
        
        # Resolve db and quarantine paths to display on the dashboard
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = args.db if args.db else os.path.join(base_dir, "..", "data", "transactions.db")
        quarantine_dir = args.quarantine if args.quarantine else os.path.join(base_dir, "quarantine")
        
        # Print dashboard to console
        print_dashboard(report, db_path, quarantine_dir)
        
    except Exception as e:
        print(f"\nCatastrophic error during Pipeline execution: {e}\n", file=sys.stderr)
        sys.exit(1)
