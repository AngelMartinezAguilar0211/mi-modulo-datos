import sys
import time
import uuid
import json
import numpy as np
from pathlib import Path
from fastapi.testclient import TestClient

# Automatically configure sys.path to enable importing from app
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(current_dir.parent))

from app.main import app
from app.cache import cache

def run_latency_benchmark():
    print("=" * 60)
    print("INICIANDO BENCHMARK DE LATENCIA (100 peticiones por endpoint)")
    print("=" * 60)
    
    results = {}
    
    # Initialize FastAPI TestClient which triggers the lifespan (DB connections setup)
    with TestClient(app) as client:
        # Helper to calculate percentiles from a list of latencies in ms
        def calc_percentiles(latencies):
            latencies_ms = np.array(latencies) * 1000.0  # Convert to milliseconds
            return {
                "p50": float(np.percentile(latencies_ms, 50)),
                "p95": float(np.percentile(latencies_ms, 95)),
                "p99": float(np.percentile(latencies_ms, 99)),
                "avg": float(np.mean(latencies_ms)),
                "min": float(np.min(latencies_ms)),
                "max": float(np.max(latencies_ms)),
            }

        # -------------------------------------------------------------
        # 1. GET /health
        # -------------------------------------------------------------
        print("Midiendo GET /health...")
        health_latencies = []
        for _ in range(100):
            start = time.perf_counter()
            resp = client.get("/health")
            duration = time.perf_counter() - start
            assert resp.status_code == 200
            health_latencies.append(duration)
        results["health"] = calc_percentiles(health_latencies)

        # -------------------------------------------------------------
        # 2. GET /analytics/summary (COLD - cache cleared each time)
        # -------------------------------------------------------------
        print("Midiendo GET /analytics/summary (COLD)...")
        summary_cold_latencies = []
        for _ in range(100):
            cache.clear()  # Force cold cache
            start = time.perf_counter()
            resp = client.get("/analytics/summary")
            duration = time.perf_counter() - start
            assert resp.status_code == 200
            summary_cold_latencies.append(duration)
        results["analytics_summary_cold"] = calc_percentiles(summary_cold_latencies)

        # -------------------------------------------------------------
        # 3. GET /analytics/summary (WARM - cache populated)
        # -------------------------------------------------------------
        print("Midiendo GET /analytics/summary (WARM)...")
        # Populate first
        client.get("/analytics/summary")
        summary_warm_latencies = []
        for _ in range(100):
            start = time.perf_counter()
            resp = client.get("/analytics/summary")
            duration = time.perf_counter() - start
            assert resp.status_code == 200
            summary_warm_latencies.append(duration)
        results["analytics_summary_warm"] = calc_percentiles(summary_warm_latencies)

        # -------------------------------------------------------------
        # 4. GET /analytics/top-merchants (COLD - cache cleared each time)
        # -------------------------------------------------------------
        print("Midiendo GET /analytics/top-merchants?limit=10&country=MX (COLD)...")
        top_merchants_cold_latencies = []
        for _ in range(100):
            cache.clear()  # Force cold cache
            start = time.perf_counter()
            resp = client.get("/analytics/top-merchants?limit=10&country=MX")
            duration = time.perf_counter() - start
            assert resp.status_code == 200
            top_merchants_cold_latencies.append(duration)
        results["analytics_top_merchants_cold"] = calc_percentiles(top_merchants_cold_latencies)

        # -------------------------------------------------------------
        # 5. GET /analytics/top-merchants (WARM - cache populated)
        # -------------------------------------------------------------
        print("Midiendo GET /analytics/top-merchants?limit=10&country=MX (WARM)...")
        # Populate first
        client.get("/analytics/top-merchants?limit=10&country=MX")
        top_merchants_warm_latencies = []
        for _ in range(100):
            start = time.perf_counter()
            resp = client.get("/analytics/top-merchants?limit=10&country=MX")
            duration = time.perf_counter() - start
            assert resp.status_code == 200
            top_merchants_warm_latencies.append(duration)
        results["analytics_top_merchants_warm"] = calc_percentiles(top_merchants_warm_latencies)

        # -------------------------------------------------------------
        # 6. GET /users/{user_id}/transactions (SQLite - page 1, size 20)
        # -------------------------------------------------------------
        print("Midiendo GET /users/1/transactions (SQLite)...")
        user_tx_latencies = []
        for _ in range(100):
            start = time.perf_counter()
            resp = client.get("/users/1/transactions?page=1&page_size=20")
            duration = time.perf_counter() - start
            # User 1 might not have transactions depending on the db init, but 200/404 are both fine for latency
            assert resp.status_code in (200, 404)
            user_tx_latencies.append(duration)
        results["user_transactions"] = calc_percentiles(user_tx_latencies)

        # -------------------------------------------------------------
        # 7. GET /users/{user_id}/stats (SQLite)
        # -------------------------------------------------------------
        print("Midiendo GET /users/1/stats (SQLite)...")
        user_stats_latencies = []
        for _ in range(100):
            start = time.perf_counter()
            resp = client.get("/users/1/stats")
            duration = time.perf_counter() - start
            assert resp.status_code in (200, 404)
            user_stats_latencies.append(duration)
        results["user_stats"] = calc_percentiles(user_stats_latencies)

        # -------------------------------------------------------------
        # 8. POST /transactions/batch (SQLite - 500 valid records)
        # -------------------------------------------------------------
        print("Midiendo POST /transactions/batch (500 records)...")
        batch_latencies = []
        
        # Helper to generate a valid batch of 500 unique transactions
        def generate_valid_batch(batch_size=500):
            batch = []
            for _ in range(batch_size):
                batch.append({
                    "transaction_id": str(uuid.uuid4()),
                    "timestamp": "2026-05-19T12:00:00",
                    "user_id": 100,  # Valid range: 1 to 50000
                    "merchant_id": 500,  # Valid range: 1 to 10000
                    "amount": 99.99,  # Valid range: >= 0.01
                    "category": "Food",  # Valid category
                    "country_code": "MX",  # Valid country
                    "status": "completed"  # Valid status
                })
            return batch

        for i in range(100):
            payload = generate_valid_batch(500)
            start = time.perf_counter()
            resp = client.post("/transactions/batch", json=payload)
            duration = time.perf_counter() - start
            assert resp.status_code == 200
            batch_latencies.append(duration)
            if (i+1) % 20 == 0:
                print(f"  Progreso batch: {i+1}/100...")
                
        results["transactions_batch"] = calc_percentiles(batch_latencies)

    # -------------------------------------------------------------
    # Print Markdown Table and Save Results
    # -------------------------------------------------------------
    print("\n" + "="*80)
    print("RESULTADOS DEL BENCHMARK DE LATENCIA (en milisegundos - ms)")
    print("="*80)
    print(f"{'Endpoint / Escenario':<40} | {'p50 (Median)':<12} | {'p95':<12} | {'p99':<12} | {'Average':<12}")
    print("-" * 97)
    for name, metrics in results.items():
        print(f"{name:<40} | {metrics['p50']:>10.2f} ms | {metrics['p95']:>10.2f} ms | {metrics['p99']:>10.2f} ms | {metrics['avg']:>10.2f} ms")
    print("="*80)

    # Write output to JSON
    results_path = current_dir / "results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    print(f"Resultados guardados exitosamente en: {results_path}")

    # Write output to Markdown report (latency_report.md)
    report_path = current_dir / "latency_report.md"
    
    slas = {
        "health": 50.0,
        "analytics_summary_cold": 500.0,
        "analytics_summary_warm": 20.0,
        "analytics_top_merchants_cold": 500.0,
        "analytics_top_merchants_warm": 20.0,
        "user_transactions": 80.0,
        "user_stats": 80.0,
        "transactions_batch": 2000.0
    }
    
    display_names = {
        "health": "**`GET /health`**",
        "analytics_summary_cold": "**`GET /analytics/summary` (Cold)**",
        "analytics_summary_warm": "**`GET /analytics/summary` (Warm)**",
        "analytics_top_merchants_cold": "**`GET /analytics/top-merchants` (Cold)**",
        "analytics_top_merchants_warm": "**`GET /analytics/top-merchants` (Warm)**",
        "user_transactions": "**`GET /users/{id}/transactions`**",
        "user_stats": "**`GET /users/{id}/stats`**",
        "transactions_batch": "**`POST /transactions/batch`** (500 tx)"
    }
    
    table_rows = []
    for key in ["health", "analytics_summary_cold", "analytics_summary_warm", "analytics_top_merchants_cold", "analytics_top_merchants_warm", "user_transactions", "user_stats", "transactions_batch"]:
        m = results[key]
        limit = slas[key]
        status = "**SLA CUMPLIDO**" if m["avg"] < limit else "**SLA INCUMPLIDO**"
        table_rows.append(
            f"| {display_names[key]} | < {limit:.1f} ms | **{m['p50']:.2f} ms** | {m['p95']:.2f} ms | {m['p99']:.2f} ms | {m['avg']:.2f} ms | {status} |"
        )
        
    table_header = "| Endpoint / Escenario | SLA Requerido | p50 (Mediana) | p95 | p99 | Promedio | Estado |\n| :--- | :--- | :---: | :---: | :---: | :---: | :---: |\n"
    table_content = table_header + "\n".join(table_rows) + "\n"
    
    new_section = (
        "## Tabla Comparativa de Resultados\n\n"
        "Las mediciones se capturaron en milisegundos (ms) utilizando `time.perf_counter()` "
        "en peticiones HTTP completas a través de `TestClient`:\n\n"
        f"{table_content}"
    )
    
    if report_path.exists():
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        section_start_str = "## Tabla Comparativa de Resultados"
        if section_start_str in content:
            start_idx = content.find(section_start_str)
            search_area = content[start_idx + len(section_start_str):]
            
            end_markers = ["\n---", "\n##"]
            end_idx_relative = -1
            for marker in end_markers:
                idx = search_area.find(marker)
                if idx != -1:
                    if end_idx_relative == -1 or idx < end_idx_relative:
                        end_idx_relative = idx
                        
            if end_idx_relative != -1:
                end_idx = start_idx + len(section_start_str) + end_idx_relative
                content = content[:start_idx] + new_section + content[end_idx:]
            else:
                content = content[:start_idx] + new_section
        else:
            if not content.endswith("\n"):
                content += "\n"
            content += f"\n---\n\n{new_section}"
    else:
        content = f"""# Reporte de Latencia - Ejercicio 4: El Sistema Completo

Este reporte documenta los resultados obtenidos al ejecutar el benchmark de latencia automatizado en el sistema FastAPI dual (SQLite / DuckDB).

---

{new_section}
"""

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Reporte de latencia en Markdown actualizado quirúrgicamente en: {report_path}")

if __name__ == "__main__":
    run_latency_benchmark()
