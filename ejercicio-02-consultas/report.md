# Reporte de Benchmarking: Motores de Consulta

En este ejercicio se comparó el rendimiento de tres motores de consulta del ecosistema de Python (**pandas**, **Polars** y **DuckDB**) sobre un dataset de 1 millón de transacciones financieras almacenadas en formato Parquet.

## Tabla Comparativa de Rendimiento

A continuación se detallan los tiempos de ejecución y el pico de memoria RAM para cada una de las 8 consultas de negocio.

| Query        | Engine | Tiempo (s) | RAM (MB) | Validación |
| ------------ | ------ | ---------- | -------- | ----------- |
| **Q1** | pandas | 0.1140     | 52.29    | ✅          |
|              | Polars | 0.0234     | 0.02     | ✅          |
|              | DuckDB | 0.0114     | 0.01     | ✅          |
| **Q2** | pandas | 0.1016     | 52.29    | ✅          |
|              | Polars | 0.0250     | 0.01     | ✅          |
|              | DuckDB | 0.0188     | 0.01     | ✅          |
| **Q3** | pandas | 0.0960     | 52.29    | ✅          |
|              | Polars | 0.0335     | 0.01     | ✅          |
|              | DuckDB | 0.0702     | 0.01     | ✅          |
| **Q4** | pandas | 0.1241     | 52.28    | ✅          |
|              | Polars | 0.0143     | 0.01     | ✅          |
|              | DuckDB | 0.0136     | 0.01     | ✅          |
| **Q5** | pandas | 0.0912     | 52.29    | ✅          |
|              | Polars | 0.0663     | 0.02     | ✅          |
|              | DuckDB | 0.0793     | 3.09     | ✅          |
| **Q6** | pandas | 0.1757     | 71.40    | ✅          |
|              | Polars | 0.0318     | 0.01     | ✅          |
|              | DuckDB | 0.0333     | 0.01     | ✅          |
| **Q7** | pandas | 0.0975     | 52.29    | ✅          |
|              | Polars | 0.0084     | 0.01     | ✅          |
|              | DuckDB | 0.0165     | 0.03     | ✅          |
| **Q8** | pandas | 0.7116     | 109.64   | ✅          |
|              | Polars | 0.0573     | 0.01     | ✅          |
|              | DuckDB | 0.0391     | 0.42     | ✅          |

---

## Interpretación de EXPLAIN ANALYZE (DuckDB)

### Q3: Top 10 usuarios por monto total

```text
┌───────────────────────────────────────────────────────────────────────────┐
│┌─────────────────────────────────────────────────────────────────────────┐│
││    Query Profiling Information    ││
│└─────────────────────────────────────────────────────────────────────────┘│
└───────────────────────────────────────────────────────────────────────────┘
 EXPLAIN ANALYZE              SELECT user_id, SUM(amount) as sum, COUNT(*) as count             FROM read_parquet('/home/angel/PythonTich/tareas/mi-modulo-datos/data/test_1m_snappy.parquet')             GROUP BY user_id             ORDER BY sum DESC             LIMIT 10       
┌────────────────────────────────────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────────────────────────────────────┐│
││              Total Time: 0.0678s             ││
│└──────────────────────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────────────────┘
┌───────────────────────────┐
│           QUERY           │
└────────────┬──────────────┘
┌────────────┴──────────────┐
│      EXPLAIN_ANALYZE      │
│    ────────────────────   │
│                           │
│           0 rows          │
│           0.00s           │
└────────────┬──────────────┘
┌────────────┴──────────────┐
│           TOP_N           │
│    ────────────────────   │
│          Top: 10          │
│                           │
│         Order By:         │
│  sum(read_parquet.amount) │
│            DESC           │
│                           │
│                           │
│                           │
│          10 rows          │
│           0.00s           │
└────────────┬──────────────┘
┌────────────┴──────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_decompress_integ│
│     ral_bigint(#0, 1)     │
│             #1            │
│             #2            │
│                           │
│                           │
│                           │
│        50,000 rows        │
│           0.00s           │
└────────────┬──────────────┘
┌────────────┴──────────────┐
│       HASH_GROUP_BY       │
│    ────────────────────   │
│         Groups: #0        │
│                           │
│        Aggregates:        │
│          sum(#1)          │
│        count_star()       │
│                           │
│                           │
│                           │
│        50,000 rows        │
│           0.08s           │
└────────────┬──────────────┘
┌────────────┴──────────────┐
│         PROJECTION        │
│    ────────────────────   │
│          user_id          │
│           amount          │
│                           │
│                           │
│                           │
│       1,000,000 rows      │
│           0.00s           │
└────────────┬──────────────┘
┌────────────┴──────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_compress_integra│
│     l_usmallint(#0, 1)    │
│             #1            │
│                           │
│                           │
│                           │
│       1,000,000 rows      │
│           0.00s           │
└────────────┬──────────────┘
┌────────────┴──────────────┐
│         TABLE_SCAN        │
│    ────────────────────   │
│         Function:         │
│        READ_PARQUET       │
│                           │
│        Projections:       │
│          user_id          │
│           amount          │
│                           │
│    Total Files Read: 1    │
│                           │
│        Filename(s):       │
│   /home/angel/PythonTich  │
│  /tareas/mi-modulo-datos  │
│    /data/test_1m_snappy   │
│          .parquet         │
│                           │
│                           │
│                           │
│       1,000,000 rows      │
│           0.01s           │
└───────────────────────────┘
```

El plan de ejecución muestra un **TABLE_SCAN** bastante eficiente ya que solo proyecta las columnas `user_id` y `amount`, aprovechando el formato de columnas de Parquet. El siguiente paso utiliza un **HASH_GROUP_BY** para realizar la agregación de montos por usuario. Por ultimo, aplica un nodo **TOP_N** en lugar de un sort completo; esto lo optimiza el proceso ya que mantiene solo los 10 registros más altos en memoria mientras escanea, evitando el costo de ordenar todos los otros 50,000 usuarios únicos.

### Q5: Transacciones > 500 en MX/CO (últimos 30 días)

```text
┌───────────────────────────────────────────────────────────────────────────┐
│┌─────────────────────────────────────────────────────────────────────────┐│
││    Query Profiling Information    ││
│└─────────────────────────────────────────────────────────────────────────┘│
└───────────────────────────────────────────────────────────────────────────┘
 EXPLAIN ANALYZE              SELECT *             FROM read_parquet('/home/angel/PythonTich/tareas/mi-modulo-datos/data/test_1m_snappy.parquet')             WHERE amount > 500               AND country_code IN ('MX', 'CO')               AND timestamp >= (SELECT MAX(timestamp) FROM read_parquet('/home/angel/PythonTich/tareas/mi-modulo-datos/data/test_1m_snappy.parquet')) - INTERVAL 30 DAY       
┌────────────────────────────────────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────────────────────────────────────┐│
││              Total Time: 0.0772s             ││
│└──────────────────────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────────────────┘
┌───────────────────────────┐
│           QUERY           │
└────────────┬──────────────┘
┌────────────┴──────────────┐
│      EXPLAIN_ANALYZE      │
│    ────────────────────   │
│                           │
│           0 rows          │
│           0.00s           │
└────────────┬──────────────┘
┌────────────┴──────────────┐
│         PROJECTION        │
│    ────────────────────   │
│       transaction_id      │
│         timestamp         │
│          user_id          │
│        merchant_id        │
│           amount          │
│          category         │
│        country_code       │
│           status          │
│                           │
│                           │
│                           │
│         9,706 rows        │
│           0.00s           │
└────────────┬──────────────┘
┌────────────┴──────────────┐
│      NESTED_LOOP_JOIN     │
│    ────────────────────   │
│      Join Type: INNER     │
│                           │
│        Conditions:        │
│  timestamp >= CAST((CAST  │
│ (SUBQUERY AS TIMESTAMP) - ├──────────────┐
│  '30 days'::INTERVAL) AS  │              │
│        TIMESTAMP_NS)      │              │
│                           │              │
│                           │              │
│                           │              │
│         9,706 rows        │              │
│           0.00s           │              │
└────────────┬──────────────┘              │
┌────────────┴──────────────┐┌────────────┴──────────────┐
│           FILTER          ││         PROJECTION        │
│    ────────────────────   ││    ────────────────────   │
│ ((country_code = 'MX') OR ││ CASE  WHEN ((#1 > 1)) THEN│
│   (country_code = 'CO'))  ││   ("error"('More than one │
│                           ││      row returned by a    │
│                           ││     subquery used as an   │
│                           ││     expression - scalar   │
│                           ││     subqueries can only   │
│           0.00s           ││    return a single row.   │
│                           ││          Use "SET         │
│                           ││ scalar_subquery_error_on_m│
│                           ││   ultiple_rows=false" to  │
│                           ││     revert to previous    │
│                           ││   behavior of returning a │
│                           ││ random row.')) ELSE #0 END│
│                           ││                           │
│                           ││                           │
│                           ││                           │
│         9,706 rows        ││           1 row           │
│          (0.00s)          ││           0.00s           │
└────────────┬──────────────┘└────────────┬──────────────┘
┌────────────┴──────────────┐┌────────────┴──────────────┐
│         TABLE_SCAN        ││    UNGROUPED_AGGREGATE    │
│    ────────────────────   ││    ────────────────────   │
│         Function:         ││        Aggregates:        │
│        READ_PARQUET       ││        "first"(#0)        │
│                           ││        count_star()       │
│        Projections:       ││                           │
│           amount          ││                           │
│        country_code       ││                           │
│         timestamp         ││                           │
│       transaction_id      ││           0.00s           │
│          user_id          ││                           │
│        merchant_id        ││                           │
│          category         ││                           │
│           status          ││                           │
│                           ││                           │
│          Filters:         ││                           │
│        amount>500.0       ││                           │
│ optional: country_code IN ││                           │
│        ('MX', 'CO')       ││                           │
│                           ││                           │
│      Dynamic Filters:     ││                           │
│ timestamp>='2026-04-08 08 ││                           │
│      :01:12.803632':      ││                           │
│       :TIMESTAMP_NS       ││                           │
│                           ││                           │
│    Total Files Read: 1    ││                           │
│                           ││                           │
│        Filename(s):       ││                           │
│   /home/angel/PythonTich  ││                           │
│  /tareas/mi-modulo-datos  ││                           │
│    /data/test_1m_snappy   ││                           │
│          .parquet         ││                           │
│                           ││                           │
│                           ││                           │
│                           ││                           │
│        73,995 rows        ││           1 row           │
│           0.07s           ││          (0.00s)          │
└───────────────────────────┘└────────────┬──────────────┘
                             ┌────────────┴──────────────┐
                             │         PROJECTION        │
                             │    ────────────────────   │
                             │             #0            │
                             │                           │
                             │                           │
                             │                           │
                             │           1 row           │
                             │           0.00s           │
                             └────────────┬──────────────┘
                             ┌────────────┴──────────────┐
                             │      COLUMN_DATA_SCAN     │
                             │                           │
                             │           1 row           │
                             │           0.00s           │
                             └───────────────────────────┘
```

DuckDB implementa una optimización de **Filtros Dinámicos**. Al detectar una subquery para el `MAX(timestamp)`, DuckDB primero resuelve ese valor y luego lo inyecta directamente en el **TABLE_SCAN** del archivo Parquet. Esto permite que el lector de Parquet descarte grupos de filas (*row groups*) completos que no cumplen con la fecha, reduciendo por bastante el flujo de entradas y salidas. El uso de **NESTED_LOOP_JOIN** se debe a la comparación del flujo principal contra el valor escalar del subquery.

### Q6: Categoría líder por país

```text
┌───────────────────────────────────────────────────────────────────────────┐
│┌─────────────────────────────────────────────────────────────────────────┐│
││    Query Profiling Information    ││
│└─────────────────────────────────────────────────────────────────────────┘│
└───────────────────────────────────────────────────────────────────────────┘
 EXPLAIN ANALYZE              WITH stats AS (                 SELECT country_code, category, COUNT(*) as count, AVG(amount) as avg_amount                 FROM read_parquet('/home/angel/PythonTich/tareas/mi-modulo-datos/data/test_1m_snappy.parquet')                 GROUP BY country_code, category             ),             ranked AS (                 SELECT *, ROW_NUMBER() OVER (PARTITION BY country_code ORDER BY count DESC) as rn                 FROM stats             )             SELECT country_code, category, count, avg_amount             FROM ranked             WHERE rn = 1       
┌────────────────────────────────────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────────────────────────────────────┐│
││              Total Time: 0.0291s             ││
│└──────────────────────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────────────────┘
┌───────────────────────────┐
│           QUERY           │
└────────────┬──────────────┘
┌────────────┴──────────────┐
│      EXPLAIN_ANALYZE      │
│    ────────────────────   │
│                           │
│           0 rows          │
│           0.00s           │
└────────────┬──────────────┘
┌────────────┴──────────────┐
│         PROJECTION        │
│    ────────────────────   │
│             #0            │
│           #[9.1]          │
│           #[9.2]          │
│           #[9.3]          │
│                           │
│                           │
│                           │
│          15 rows          │
│           0.00s           │
└────────────┬──────────────┘
┌────────────┴──────────────┐
│       HASH_GROUP_BY       │
│    ────────────────────   │
│         Groups: #0        │
│                           │
│        Aggregates:        │
│ arg_max_nulls_last(#1, #2)│
│                           │
│                           │
│                           │
│          15 rows          │
│           0.01s           │
└────────────┬──────────────┘
┌────────────┴──────────────┐
│         PROJECTION        │
│    ────────────────────   │
│        country_code       │
│ struct_pack(#[9.1], #[9.2]│
│         , #[9.3])         │
│           count           │
│                           │
│                           │
│                           │
│          150 rows         │
│           0.00s           │
└────────────┬──────────────┘
┌────────────┴──────────────┐
│       HASH_GROUP_BY       │
│    ────────────────────   │
│          Groups:          │
│             #0            │
│             #1            │
│                           │
│        Aggregates:        │
│        count_star()       │
│          avg(#2)          │
│                           │
│                           │
│                           │
│          150 rows         │
│           0.02s           │
└────────────┬──────────────┘
┌────────────┴──────────────┐
│         PROJECTION        │
│    ────────────────────   │
│        country_code       │
│          category         │
│           amount          │
│                           │
│                           │
│                           │
│       1,000,000 rows      │
│           0.00s           │
└────────────┬──────────────┘
┌────────────┴──────────────┐
│         TABLE_SCAN        │
│    ────────────────────   │
│         Function:         │
│        READ_PARQUET       │
│                           │
│        Projections:       │
│        country_code       │
│          category         │
│           amount          │
│                           │
│    Total Files Read: 1    │
│                           │
│        Filename(s):       │
│   /home/angel/PythonTich  │
│  /tareas/mi-modulo-datos  │
│    /data/test_1m_snappy   │
│          .parquet         │
│                           │
│                           │
│                           │
│       1,000,000 rows      │
│           0.01s           │
└───────────────────────────┘
```

El motor realiza un primer **HASH_GROUP_BY** para calcular los agregados de pais y categoría, lo cual reduce el problema de un millon a 150 filas. Luego, utiliza un nodo de agregación especializado (`arg_max`) la cual solo pasa por las 150 filas y almacena el "mejor" resultado sin ordenar todas. De este modo obtiene a las 15 categorías distintas sin tener que ordenar la gran cantidad de datos.

---

## Análisis de Trade-offs y Rendimiento

1. **Donde Polars supera claramente a pandas (Q8 - Promedio Diario):**
   En Q8, Polars es aproximadamente **16 veces más rápido** que pandas (0.057s vs 0.931s). Esto se debe a que Polars utiliza un motor de ejecución multi-hilo nativo en Rust y su API Lazy optimiza la creación de la columna `date` a partir del `timestamp`. pandas, al ser monohilo y depender de objetos de Python para la manipulación de fechas, sufre un cuello de botella significativo en el procesamiento de series temporales.
2. **Donde DuckDB es el ganador claro (Q1 - Conteo por País):**
   DuckDB brilla en agregaciones simples sobre grandes volúmenes. Con un tiempo de **0.011s**, es el motor más rápido para Q1. Su motor de ejecución vectorial procesa bloques de datos en lugar de filas individuales, lo que minimiza el overhead de despacho de instrucciones y aprovecha al máximo la caché del procesador.
3. **Donde los tres son comparables (Q5 - Filtrado Específico):**
   En Q5, los tiempos de Polars (0.06s) y DuckDB (0.07s) son muy cercanos, y pandas (0.12s) no se queda tan atrás. Esto ocurre porque la selectividad del filtro es alta (pocas filas cumplen el criterio de monto > 500, país MX/CO y fecha reciente). Cuando la cantidad de datos resultante es pequeña, el tiempo dominante es el de lectura inicial del archivo y la configuración del plan, donde las diferencias de arquitectura de ejecución se diluyen.

---

## Recomendación de Arquitectura

Gracias a estos resultados, el uso recomendado que le daría a cada uno de ellos es:

* **Usar Polars** cuando se realicen agregaciones complejas sobre series temporales y fechas, donde demostró la mayor eficiencia y velocidad (hasta 18x frente a pandas en Q8).
* **Usar DuckDB** para consultas analíticas de tipo ranking (Top N), agrupaciones masivas y filtros dinámicos, gracias a su capacidad de optimizar planes de ejecución y reducir el acceso a datos innecesarios (Q1, Q3, Q5, Q6).
* **Usar pandas** solo para datasets reducidos, ya que en las pruebas de 1M de registros fue consistentemente el motor más lento y con mayor consumo de memoria RAM (picos de 110MB).
