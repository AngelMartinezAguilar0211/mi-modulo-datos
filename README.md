# Módulo: Python para Sistemas de Datos Modernos

Este repositorio contiene las soluciones a los ejercicios prácticos de Python, diseñados para construir un sistema de datos moderno de extremo a extremo, abarcando evaluación de formatos, motores de querys, base transaccional de datos y un API serving layer.

## Ejercicio 1: Formatos Bajo la Lupa

Este primer ejercicio se centra en demostrar de forma empírica y técnica las diferencias de rendimiento (tiempo de lectura, tiempo de escritura, uso de RAM y tamaño en disco) entre formatos orientados a filas (CSV, JSON Lines) y orientados a columnas (Parquet con sus distintas compresiones).

### Requisitos Previos

Encontrarse en la raíz de este repositorio y contar con el gestor de entornos `uv` correctamente instalado. Las dependencias ya están declaradas en el proyecto. 

Para asegurar que el entorno está listo:
```bash
uv sync  # O si recién clonas, se instalarán automáticamente al usar `uv run`
```

### Guía de Ejecución

Todos los scripts relacionados con este módulo se encuentran en la carpeta `ejercicio-01-formatos`. Navega hacia ella antes de ejecutar los comandos:

```bash
cd ejercicio-01-formatos
```

#### 1. Generación de Datos (Opcional: Independiente)
Si se desea generar una muestra del dataset CSV de manera aislada:
```bash
uv run python generate_data.py --size 1m
```
*Tamaños aceptados: `100k`, `500k` y `1m`.*

#### 2. Ejecutar el Benchmark Principal
Este es el comando principal. El CLI orquestará la generación de la data en memoria y evaluará el rendimiento de cada uno de los formatos solicitados.

```bash
uv run python benchmark_cli.py --size 1m --formats csv jsonl parquet_uncompressed parquet_snappy parquet_gzip
```
> **Nota:** Puedes correr esto para `--size 100k` y `--size 500k` para tener comparativas a diferentes escalas. Los resultados en bruto se guardarán automáticamente en `results/benchmark_<size>.json`.

#### 3. Generar la Base del Reporte
Una vez que hayas completado el benchmark, puedes generar automáticamente la base del reporte ejecutando:

```bash
uv run python plot_results.py
```
> **Nota:** Esto creará el archivo `report.md` con tablas y gráficas incrustadas.
