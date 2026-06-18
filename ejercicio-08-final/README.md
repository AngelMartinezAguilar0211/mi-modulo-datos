# Ejercicio 8: Proyecto Final — Sistema de Monitoreo Transaccional Fintech LATAM

Sistema completo de monitoreo de transacciones para una fintech LATAM. Integra los mejores componentes de los ejercicios 4 al 7: API REST con FastAPI, motor dual SQLite/DuckDB, pipeline ETL para ingesta de CSV, detección de anomalías, y contenerización con Docker.

---

## Arquitectura

| Capa | Tecnología | Propósito |
|------|-----------|-----------|
| API | FastAPI + Uvicorn | 8 endpoints REST con validación Pydantic |
| OLTP | SQLite (WAL mode) | Consultas transaccionales: usuarios, inserciones, anomalías |
| OLAP | DuckDB (in-memory) | Consultas analíticas: resúmenes, top merchants (sobre Parquet) |
| Pipeline | stdlib Python (csv, sqlite3) | Ingesta de CSV externo con validación y cuarentena |
| Contenedores | Docker multi-stage | Imagen <300MB, compose con setup + API |

---

## Prerrequisitos

- Docker y Docker Compose instalados
- Archivo `test_1m_snappy.parquet` en la carpeta `data/` (generado en el E01)

---

## Guía Operacional de Comandos

Todos los comandos se ejecutan desde la raíz de `ejercicio-08-final/`:

### 1. Levantar el sistema desde cero

```bash
docker compose up --build
```

### 2. Verificar que está corriendo

```bash
docker compose ps
curl http://localhost:8000/health
```

### 3. Ver los logs en tiempo real

```bash
docker compose logs -f api
```

### 4. Parar y limpiar todo

```bash
docker compose down -v
```

---

## Endpoints Disponibles

### Analítica (DuckDB / Parquet)

#### `GET /analytics/summary` — Volumen global por país y categoría

```bash
curl http://localhost:8000/analytics/summary
```

#### `GET /analytics/top-merchants` — Top merchants por volumen

```bash
curl "http://localhost:8000/analytics/top-merchants?limit=5"
curl "http://localhost:8000/analytics/top-merchants?limit=3&country=MX"
```

#### `GET /analytics/anomalies` — Detección de anomalías

Retorna usuarios con más de N transacciones fallidas en los últimos 30 días:

```bash
curl "http://localhost:8000/analytics/anomalies"
curl "http://localhost:8000/analytics/anomalies?threshold=10"
```

### Usuarios (SQLite)

#### `GET /users/{user_id}/transactions` — Historial con filtros de fecha

```bash
curl "http://localhost:8000/users/1/transactions?page=1&page_size=10"
curl "http://localhost:8000/users/1/transactions?date_from=2026-01-01&date_to=2026-06-30"
```

#### `GET /users/{user_id}/stats` — Estadísticas de usuario

```bash
curl http://localhost:8000/users/1/stats
```

### Escritura

#### `POST /transactions/batch` — Inserción idempotente de batch

```bash
curl -X POST http://localhost:8000/transactions/batch \
  -H "Content-Type: application/json" \
  -d '[{
    "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-06-10T10:00:00",
    "user_id": 42,
    "merchant_id": 99,
    "amount": 150.75,
    "category": "Food",
    "country_code": "MX",
    "status": "completed"
  }]'
```

### Pipeline

#### `POST /pipeline/ingest` — Ingesta de archivo CSV

```bash
curl -F "file=@mi_archivo.csv" http://localhost:8000/pipeline/ingest
```

### Sistema

#### `GET /health` — Estado del sistema

```bash
curl http://localhost:8000/health
```

---

## Correr los Tests

Desde la raíz del repositorio (`mi-modulo-datos/`):

```bash
cd ejercicio-08-final
uv run pytest tests/ -v
```

---

## Estructura del Proyecto

```
ejercicio-08-final/
├── app/
│   ├── main.py          # FastAPI app (8 endpoints)
│   ├── db.py            # DatabaseManager (SQLite + DuckDB)
│   ├── cache.py         # TTL cache thread-safe
│   └── models.py        # Pydantic models + domain constants
├── pipeline/
│   ├── extract_csv.py   # CSV extraction + normalization
│   ├── transform.py     # Business rules validation + quarantine
│   ├── load.py          # Transactional SQLite loader
│   └── ingest.py        # Pipeline orchestrator
├── setup/
│   └── db_setup.py      # One-shot Parquet → SQLite ingestion
├── tests/
│   ├── conftest.py      # Test fixtures
│   ├── test_api.py      # 15 API endpoint tests
│   ├── test_anomalies.py # 5 anomaly detection tests
│   └── test_pipeline.py # 9 pipeline tests
├── Dockerfile           # Multi-stage API image (<300MB)
├── Dockerfile.setup     # One-shot setup image
├── docker-compose.yml   # Orchestration (setup → api)
├── .env.example         # Environment variables template
├── decisions.md         # Technical decisions document
└── README.md
```
