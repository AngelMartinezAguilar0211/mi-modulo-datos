# Ejercicio 4: El Sistema Completo

Este proyecto implementa una API REST utilizando **FastAPI** con una **arquitectura dual de base de datos** (SQLite para transacciones rápidas OLTP y DuckDB para consultas analíticas pesadas OLAP sobre archivos Parquet), respaldada por una capa de caché en memoria con TTL.

---

## Diagrama de Arquitectura (Dual Backend)

```text
                  +----------------------------------------------+
                  |               Cliente / HTTP                 |
                  +-----------------------+----------------------+
                                          |
                                          v  [HTTP Request]
                  +-----------------------+----------------------+
                  |                FastAPI API                   |
                  |     (Validación Pydantic / Middleware)       |
                  +-----------------------+----------------------+
                                          |
                     +--------------------+--------------------+
                     |                                         |
                     |  [Endpoint Analítico / OLAP]            |  [Endpoint Transaccional / OLTP]
                     v                                         v
        +------------+------------+              +-------------+-------------+
        |   ¿Existe en Caché?     |              |     SQLite Connection     |
        +------------+------------+              |  (WAL Mode / Synchronous) |
                     |                           +-------------+-------------+
            +--------+--------+                                |
         Sí |              No |                                v
            v                 v                       +--------+--------+
      [Retornar de]    [Consultar a]                  |  Búsqueda por   |
     [Memoria O(1)]     [DuckDB Pool]                 | Índice Compuesto|
            |                 |                       +--------+--------+
            |                 v                                |
            |         +-------+-------+                        v
            |         |  Vista sobre  |                  [Retornar /]
            |         |  Parquet 1M   |                  [Insertar  ]
            |         +-------+-------+                        |
            |                 |                                |
            +-----------------+---------------+----------------+
                              |               |
                              v               v
                        [HTTP Response / JSON payload]
```

---

## Requerimientos y Preparación del Entorno

Se debe contar con `uv` instalado globalmente en el sistema. Si no se tiene, se puede instalar con:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Las dependencias del proyecto se gestionan en la raíz de `mi-modulo-datos/` mediante `pyproject.toml`.
Una vez instalado `uv`, se pueden instalar las dependencias del proyecto ejecutando el siguiente comando en el directorio raíz:
```bash
uv sync
```

---

## Variables de Entorno Soportadas

Se puede configurar el comportamiento del servidor a través de las siguientes variables de entorno:

| Variable | Descripción | Valor por Defecto |
| :--- | :--- | :--- |
| `SQLITE_DB_PATH` | Ruta absoluta o relativa al archivo de base de datos SQLite. | `../data/transactions.db` |
| `PARQUET_FILE_PATH` | Ruta absoluta o relativa al dataset Parquet. | `../data/test_1m_snappy.parquet` |
| `CACHE_TTL` | Tiempo de vida (TTL) en segundos para la caché analítica. | `60` |

---

## Ejecución del Servidor

Para iniciar el servidor de desarrollo FastAPI con recarga en caliente (`reload`), se debe ingresar al directorio del ejercicio `ejercicio-04-sistema` desde la raíz de `mi-modulo-datos/` y ejecutar `uvicorn`:

```bash
cd ejercicio-04-sistema
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

El servidor estará disponible en [http://127.0.0.1:8000](http://127.0.0.1:8000) y la documentación interactiva OpenAPI (Swagger UI) se podrá explorar en [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

---

## Ejecución de la Suite de Pruebas

El proyecto cuenta con una suite completa de pruebas automatizadas que valida escenarios positivos, negativos y el cumplimiento de latencias.

Para ejecutar las pruebas, se debe ingresar al directorio del ejercicio `ejercicio-04-sistema` y ejecutar `pytest`:

```bash
cd ejercicio-04-sistema
uv run pytest -v tests/test_api.py
```

---

## Ejecución de los Benchmarks de Latencia

Para ejecutar la recolección automática de latencias en los 6 endpoints y generar el archivo `results.json`, se debe ingresar al directorio `ejercicio-04-sistema` y ejecutar el script correspondiente:

```bash
cd ejercicio-04-sistema
uv run python benchmarks/run_benchmark.py
```

