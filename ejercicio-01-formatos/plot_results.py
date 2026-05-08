import json
import os
import matplotlib.pyplot as plt

def bytes_to_mb(b):
    return b / (1024 * 1024)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    results_dir = os.path.join(script_dir, 'results')
    
    sizes = ['100k', '500k', '1m']
    all_data = {}
    
    for size in sizes:
        filepath = os.path.join(results_dir, f'benchmark_{size}.json')
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                all_data[size] = json.load(f)
                
    if not all_data:
        print("No benchmark results found.")
        return
        
    md = ["# Reporte de Formatos Bajo la Lupa\n"]
    md.append("## Tablas Comparativas\n")
    
    for size in sizes:
        if size not in all_data:
            continue
        data = all_data[size]
        
        # 1. Add Markdown Table
        md.append(f"### Escala: {size}")
        md.append("| Formato | Escritura (s) | Lectura Completa (s) | Lectura Selectiva (s) | Tamaño (MB) | RAM Pico (MB) |")
        md.append("|---------|---------------|----------------------|-----------------------|-------------|---------------|")
        for row in data:
            fmt = row['format']
            w = f"{row['write_time_avg']:.2f}"
            r_full = f"{row['full_read_time']:.2f}"
            r_sel = f"{row['selective_read_time']:.3f}"
            size_mb = f"{bytes_to_mb(row['file_size_bytes']):.2f}"
            ram_mb = f"{bytes_to_mb(row['peak_memory_bytes']):.2f}"
            md.append(f"| {fmt} | {w} | {r_full} | {r_sel} | {size_mb} | {ram_mb} |")
        md.append("\n")

        # 2. Add Read Time Graphs and save PNGs
        labels = [d['format'] for d in data]
        full_read = [d['full_read_time'] for d in data]
        selective_read = [d['selective_read_time'] for d in data]
        
        x = range(len(labels))
        width = 0.35
        
        fig1, ax1 = plt.subplots(figsize=(10, 6))
        ax1.bar([i - width/2 for i in x], full_read, width, label='Full Read')
        ax1.bar([i + width/2 for i in x], selective_read, width, label='Selective Read')
        
        ax1.set_ylabel('Time (seconds)')
        ax1.set_title(f'Read Time Comparison at {size} scale')
        ax1.set_xticks(x)
        ax1.set_xticklabels(labels, rotation=45)
        ax1.legend()
        fig1.tight_layout()
        read_time_path = os.path.join(results_dir, f'read_time_{size}.png')
        fig1.savefig(read_time_path, bbox_inches='tight')
        plt.close(fig1)
        
        sizes_mb_list = [bytes_to_mb(d['file_size_bytes']) for d in data]
        
        fig2, ax2 = plt.subplots(figsize=(10, 6))
        ax2.bar(labels, sizes_mb_list, color='skyblue')
        
        ax2.set_ylabel('Size (MB)')
        ax2.set_title(f'File Size Comparison at {size} scale')
        ax2.set_xticks(range(len(labels)))
        ax2.set_xticklabels(labels, rotation=45)
        
        for i, v in enumerate(sizes_mb_list):
            ax2.text(i, v + 0.5, f"{v:.1f} MB", ha='center')
            
        fig2.tight_layout()
        file_size_path = os.path.join(results_dir, f'file_size_{size}.png')
        fig2.savefig(file_size_path, bbox_inches='tight')
        plt.close(fig2)

    # 3. Add Graph Links to Markdown
    md.append("## Gráficas de Rendimiento\n")
    for size in sizes:
        if size in all_data:
            md.append(f"### Escala {size}")
            md.append(f"![Tiempo de Lectura {size}](results/read_time_{size}.png)")
            md.append(f"![Tamaño en Disco {size}](results/file_size_{size}.png)\n")

    # 4. Preserve conclusions
    report_path = os.path.join(script_dir, 'report.md')
    existing_conclusions = ""
    if os.path.exists(report_path):
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if '## Conclusiones Técnicas y Análisis' in content:
                existing_conclusions = '## Conclusiones Técnicas y Análisis' + content.split('## Conclusiones Técnicas y Análisis')[1]
                
    if existing_conclusions:
        md.append(existing_conclusions)
    else:
        # Template for analysis
        md.append("""## Conclusiones Técnicas y Análisis

*(Escribe aquí tus conclusiones técnicas. Asegúrate de explicar POR QUÉ ocurren las diferencias, enfocándote en la orientación a filas vs columnas, tipo de compresión, costo de CPU al parsear texto vs formatos binarios, etc.)*

## Recomendación para Producción

*(Escribe aquí qué formato usarías en producción y por qué)*
""")

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(md))
        
    print(f"Graphs saved in {results_dir}")
    print(f"Report updated at {report_path} (Conclusions preserved)")

if __name__ == '__main__':
    main()
