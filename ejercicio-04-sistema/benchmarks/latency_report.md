# Reporte de Latencia - Ejercicio 4: El Sistema Completo

Este reporte documenta los resultados obtenidos al ejecutar el benchmark de latencia automatizado en el sistema FastAPI dual (SQLite / DuckDB) con caché activa en memoria.

El benchmark consistió en realizar **100 peticiones consecutivas** para cada endpoint o escenario para medir y analizar la distribución de la latencia (percentiles p50, p95, p99 y promedio).

---

## Tabla Comparativa de Resultados

Las mediciones se capturaron en milisegundos (ms) utilizando `time.perf_counter()` en peticiones HTTP completas a través de `TestClient`:

| Endpoint / Escenario | SLA Requerido | p50 (Mediana) | p95 | p99 | Promedio | Estado |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`GET /health`** | < 50.0 ms | **0.80 ms** | 1.12 ms | 1.63 ms | 0.87 ms | **SLA CUMPLIDO** |
| **`GET /analytics/summary` (Cold)** | < 500.0 ms | **33.30 ms** | 38.01 ms | 44.60 ms | 33.85 ms | **SLA CUMPLIDO** |
| **`GET /analytics/summary` (Warm)** | < 20.0 ms | **0.67 ms** | 0.94 ms | 0.98 ms | 0.69 ms | **SLA CUMPLIDO** |
| **`GET /analytics/top-merchants` (Cold)** | < 500.0 ms | **14.22 ms** | 17.82 ms | 39.25 ms | 18.03 ms | **SLA CUMPLIDO** |
| **`GET /analytics/top-merchants` (Warm)** | < 20.0 ms | **0.63 ms** | 0.85 ms | 0.97 ms | 0.65 ms | **SLA CUMPLIDO** |
| **`GET /users/{id}/transactions`** | < 80.0 ms | **0.87 ms** | 1.33 ms | 9.22 ms | 1.20 ms | **SLA CUMPLIDO** |
| **`GET /users/{id}/stats`** | < 80.0 ms | **0.62 ms** | 0.78 ms | 0.94 ms | 0.64 ms | **SLA CUMPLIDO** |
| **`POST /transactions/batch`** (500 tx) | < 2000.0 ms | **28.84 ms** | 82.44 ms | 113.89 ms | 36.42 ms | **SLA CUMPLIDO** |

---

## Análisis del Impacto del Caché

El impacto de la capa de caché implementada en `app/cache.py` demuestra los beneficios de la arquitectura orientada a alta velocidad en lectura:

### 1. Endpoint `/analytics/summary`
- **Cold (Caché Vacío):** Registra una mediana (p50) de **33.30 ms** y un p99 de **44.60 ms**. Esto representa el tiempo que toma DuckDB en escanear en memoria el archivo Parquet de 1 millón de registros, realizar múltiples agregaciones globales y agrupaciones grupales por país y categoría, y retornar la respuesta serializada.
- **Warm (Caché Activo):** Registra una mediana (p50) de **0.67 ms** y un p99 de **0.98 ms**.
- **Factor de Aceleración:** La caché activa genera un incremento de velocidad de **~49.7x** (aproximadamente un 4,870% más veloz), reduciendo la latencia de milisegundos a niveles practicamente imperceptibles.

### 2. Endpoint `/analytics/top-merchants`
- **Cold (Caché Vacío):** Registra una mediana de **14.22 ms** y un p99 de **39.25 ms**
- **Warm (Caché Activo):** Disminuye a una mediana de **0.63 ms** y un p99 de **0.97 ms**.
- **Factor de Aceleración:** Un incremento de velocidad de **~22.6x** (aproximadamente un 2,157% más veloz).

---

## Justificación del Cumplimiento de los SLAs

El sistema cumple los SLAs gracias a decisiones técnicas intencionales:

1. **Uso de Lifespan en la Conexión a la Base de Datos:**
   Al inicializar las conexiones de SQLite y DuckDB en el startup (`lifespan`) de la aplicación y mantenerlas abiertas a nivel global en `app/db.py`, se elimina por completo la penalización de ~5ms-15ms asociada a abrir y cerrar conexiones de archivos en disco por cada request.
   
2. **Capa Transaccional Indexada en SQLite:**
   Los endpoints transaccionales del usuario (`/users/{id}/transactions` y `/users/{id}/stats`) consultan directamente índices óptimos en SQLite. Esto permite que SQLite ubique y retorne los registros en menos de **1 ms** en el p50.

3. **Ingesta Batch con Transacción Única Explicita:**
   El endpoint `POST /transactions/batch` realiza inserciones masivas de hasta 500 transacciones. Si se hiciera commit individual por fila, la latencia superaría con creces los 2 segundos debido al retardo I/O del disco duro. Al envolver todo el lote de 500 registros dentro de un bloque explícito `BEGIN TRANSACTION;` y `COMMIT;` en SQLite, la latencia promedio del batch entero es de tan solo **36.42 ms**.
