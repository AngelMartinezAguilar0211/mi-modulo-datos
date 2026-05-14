import json
import re
import os

def update_report():
    # Rutas relativas al directorio del script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, 'results', 'benchmark_results.json')
    report_path = os.path.join(script_dir, 'report.md')
    
    if not os.path.exists(json_path):
        print(f"Error: {json_path} no encontrado. Ejecuta primero el benchmark.")
        return

    print(f"Leyendo resultados de {json_path}...")
    with open(json_path, 'r') as f:
        data = json.load(f)

    with open(report_path, 'r') as f:
        report_content = f.read()

    # 1. Actualizar la Tabla Comparativa Principal
    print("Actualizando tabla comparativa principal...")
    for query_res in data['results']:
        q_id = query_res['query']
        metrics = query_res['metrics']
        
        for engine in ['pandas', 'polars', 'duckdb']:
            m = metrics[engine]
            pattern = rf"(\| (?:(?:\*\*{q_id}\*\*)|(?:\s+)) \| {engine} \|) ([\d\.]+) \| ([\d\.]+) \|"
            replacement = rf"\1 {m['time_s']:.4f} | {m['ram_mb']:.2f} |"
            report_content = re.sub(pattern, replacement, report_content, flags=re.IGNORECASE)

    # 2. Actualizar Secciones Individuales (Q1 a Q8)
    print("Actualizando tablas detalladas de Q1-Q8...")
    for query_res in data['results']:
        metrics = query_res['metrics']
        for engine_label in ['pandas', 'Polars', 'DuckDB']:
            m = metrics[engine_label.lower()]
            pattern = rf"(\| {engine_label} \|) ([\d\.]+)s \| ([\d\.]+) MB \|"
            replacement = rf"\1 {m['time_s']:.4f}s | {m['ram_mb']:.2f} MB |"
            report_content = re.sub(pattern, replacement, report_content)

    # 3. Actualizar bloques EXPLAIN ANALYZE de DuckDB
    if 'explains' in data:
        print("Actualizando planes de ejecución (EXPLAIN ANALYZE)...")
        for q_id, explain_text in data['explains'].items():
            pattern = rf"(### EXPLAIN ANALYZE \(DuckDB - {q_id}\)\n\n```text\n)([\s\S]*?)\n(```)"
            report_content = re.sub(pattern, rf"\1{explain_text}\n\3", report_content)

    with open(report_path, 'w') as f:
        f.write(report_content)
    
    print("\n✅ Reporte 'report.md' actualizado exitosamente.")

if __name__ == "__main__":
    update_report()
