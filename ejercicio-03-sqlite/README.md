# Ejercicio 3: La Capa Transaccional (SQLite)

Este ejercicio implementa una capa de almacenamiento transaccional utilizando SQLite, optimizada para consultas de baja latencia mediante el uso estratégico de índices.

## Estructura del Proyecto

- `schema.sql`: Definición de la tabla e índices.
- `schema_design.md`: Justificación técnica del diseño de la base de datos.
- `ingest.py`: Script para importar los datos desde Parquet a SQLite.
- `benchmark_queries.py`: Suite de pruebas de rendimiento para los 5 patrones de acceso.
- `results/`: Directorio con los resultados de las mediciones en formato JSON.

## Requisitos Previos

Asegúrate de tener instalado `uv` y las dependencias del proyecto:

```bash
uv sync
```

Es necesario tener el archivo `data/test_1m_snappy.parquet` generado en el Ejercicio 1.

## Instrucciones para Regenerar la Base de Datos

Para borrar la base de datos actual y regenerarla desde cero con los datos del Parquet, ejecuta:

```bash
uv run ingest.py --chunk-size 50000 --wal
```

Este comando:
1. Borra `data/transactions.db` si existe.
2. Crea la tabla e índices definidos en `schema.sql`.
3. Inserta 1 millón de registros en bloques de 50,000 filas por transacción.
4. Habilita el modo WAL para mejorar el rendimiento.

## Ejecución de Benchmarks

Para medir el rendimiento de los patrones de acceso y comparar contra DuckDB:

```bash
uv run benchmark_queries.py
```

Los resultados se guardarán en `results/query_benchmarks.json`.

## Análisis de Rendimiento: SQLite vs DuckDB

Comparé los tiempos de ejecución de los 5 patrones de acceso utilizando SQLite frente a DuckDB (leyendo directamente sobre el archivo Parquet). 

Los resultados son los siguientes:

*   **P1 (Buscar por ID exacto):** **SQLite gana por mucho (~0.04ms vs ~99ms).** Al tener un índice `PRIMARY KEY` (B-Tree), SQLite localiza la fila en tiempo $O(\log N)$ accediendo directamente a la ubicación en disco. DuckDB, al estar orientado a columnas, no tiene índices tradicionales y debe escanear los metadatos de los row groups del Parquet para encontrar el registro, lo cual es muy ineficiente para búsquedas especificas.
*   **P2 (Últimas 20 transacciones de un usuario):** **SQLite gana (~0.13ms vs ~69ms).** El índice compuesto `idx_user_timestamp` permite a SQLite saltar directamente| a los registros del usuario y leer los primeros 20 ya ordenados de forma descendente (Top-N optimization). DuckDB requiere leer los datos columnares, filtrar y luego realizar un sort en memoria.
*   **P3 (Transacciones por rango de fecha):** **SQLite gana (~0.02ms vs ~41ms).** Al igual que en P2, el índice compuesto permite a SQLite encontrar el bloque exacto de transacciones contiguas en disco para ese rango de fechas de manera casi instantánea, leyendo solo lo necesario. DuckDB continua con su proceso completo que no se le puede igualar por la cantidad de datos que lee.
*   **P4 (Suma de montos en el último mes):** **SQLite gana con índices (~0.01ms vs ~6ms de DuckDB), pero sin indices DuckDB es mas rapido (~6ms vs 36ms).** Aunque es una consulta de agregación (`SUM`), tiene un filtro muy selectivo (`user_id`). Gracias al índice compuesto, SQLite localiza instantáneamente el puñado de filas de ese usuario y las suma en microsegundos. DuckDB, aunque es rapidísimo para leer columnas (6ms es excelente frente a los 36ms de SQLite *sin* índices), tiene una sobrecarga inicial al escanear los metadatos y evaluar toda la columna, por lo que no puede igualar la precisión del B-Tree de SQLite para un solo usuario.
*   **P5 (Agrupación de usuarios frecuentes por país):** **DuckDB gana (~12ms vs ~50ms).** DuckDB procesa agregaciones y diccionarios de manera paralela mucho más rápido ya que puede leer los datos en columnas. SQLite, incluso cuando cuenta con un índice en `country_code` para filtrar primero, es más lento ya que este no reduce significativamente el número de filas a procesar y termina procesado 66,000 filas aproximadamente.

**Conclusión:**
SQLite, cuando se modela con los índices correctos, es indispensable para la capa transaccional, garantizando respuestas menores a 50ms para interacciones en tiempo real. DuckDB es el motor superior para métricas, reportes y agregaciones masivas, esto podría justificar la necesidad de una arquitectura híbrida que obtenga lo mejor de ambos mundos, SQLite para transacciones en tiempo real y DuckDB para análisis y reportes.
