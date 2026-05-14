# Módulo: Python para Sistemas de Datos Modernos

Este repositorio contiene las soluciones a los ejercicios prácticos de Python, diseñados para construir un sistema de datos moderno de extremo a extremo, abarcando evaluación de formatos, motores de querys, base transaccional de datos y un API serving layer.

## Ejercicio 1: Formatos Bajo la Lupa

Este primer ejercicio se centra en demostrar de forma empírica y técnica las diferencias de rendimiento (tiempo de lectura, tiempo de escritura, uso de RAM y tamaño en disco) entre formatos orientados a filas (CSV, JSON Lines) y orientados a columnas (Parquet con sus distintas compresiones).

**NOTA:** El repositorio ya cuenta con resultados de benchmark para 100k, 500k y 1m; así como con las graficas de resultados visibles en el reporte. Hacer un nuevo benchmark reescribirá estos archivos.

### Requisitos Previos

Encontrarse en la raíz de este repositorio y contar con el gestor de entornos `uv` correctamente instalado. Las dependencias ya están declaradas en el proyecto. 

Para asegurar que el entorno está listo:
```bash
uv sync
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
> **Nota:** Esto creará el archivo `report.md` en la raíz del ejercicio y guardará los archivos `.png` en la carpeta `results/`. 

---

## Ejercicio 2: El Motor de Consultas

En este ejercicio se implementa una suite de benchmarking para comparar tres de los motores de consulta en el ecosistema de Python: **pandas**, **Polars** y **DuckDB**. El objetivo es evaluar su rendimiento procesando un dataset de **1,000,000 de registros** en formato Parquet.

### Características Principales
- **8 Consultas de Negocio**: Desde agregaciones simples hasta ventanas de tiempo y rankings complejos.
*   **Triple Validación**: El sistema valida automáticamente que los tres motores devuelvan el mismo resultado numérico para cada consulta.
*   **Análisis de Planes**: Captura de planes de ejecución reales (`EXPLAIN ANALYZE`) para DuckDB.
*   **Métricas**: Medición precisa de tiempo (latencia) y pico de memoria RAM.

### Guía de Ejecución

Navega a la carpeta del ejercicio:
*Es necesario contar con el dataset test_1m_snappy.parquet en la carpeta data.*
```bash
cd ejercicio-02-consultas
```

Ejecuta el orquestador de benchmark:
(Por default 5 iteraciones para cada query, en otro caso usar --iters <num>)
```bash
uv run python benchmark.py --output results/
```

Para añadir automáticamente los resultados en el reporte visual (manteniendo las interpretaciones y comentarios intactos):
```bash
uv run python create_report.py
```

### Resultados y Reporte
El script generará un archivo `results/benchmark_results.json` con los datos crudos. El análisis detallado, incluyendo la interpretación de los planes de ejecución y las recomendaciones de arquitectura, se encuentra en:
👉 [**ejercicio-02-consultas/report.md**](./ejercicio-02-consultas/report.md)
