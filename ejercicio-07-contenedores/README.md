# Ejercicio 7: De tu Máquina al Mundo (Contenerización con Docker)

Este proyecto implementa la contenerización de la API REST transaccional y analítica basada en **FastAPI**, **SQLite** y **DuckDB**.

El sistema consta de dos contenedores orquestados con **Docker Compose**:
1. **`setup`**: Un contenedor *one-shot* que levanta, crea el esquema de SQLite y los índices compuestos, e ingesta el dataset Parquet de 1 millón de registros en disco utilizando DuckDB.
2. **`api`**: El servicio web de FastAPI, el cual se inicializa y arranca únicamente una vez que el contenedor `setup` ha finalizado con éxito.

---

## Prerrequisitos

Se debe de contar con Docker y Docker Compose instalados en la máquina anfitriona. Si se encuentra en una distribución basada en Ubuntu/Debian (o WSL2), puede instalarlos con:

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
# Nota: Cerrar y volver a abrir sesión para aplicar los permisos de grupo.
```

---

## Guía Operacional de Comandos

Todos los comandos presentados a continuación se encuentran verificados y deben ser ejecutados desde la raíz del directorio del ejercicio (`ejercicio-07-contenedores/`):

### 1. Cómo levantar el sistema desde cero
El siguiente comando descarga la imagen base, compila las dependencias e inicia el pipeline de base de datos seguido de la API:

```bash
docker compose up --build
```

### 2. Cómo verificar que está corriendo
Para inspeccionar que los servicios se encuentran en estado activo y saludable, y realizar una petición HTTP de verificación de salud al backend:

```bash
docker compose ps
curl http://localhost:8000/health
```

### 3. Cómo ver los logs en tiempo real
Para observar los logs estructurados del servicio de la API:

```bash
docker compose logs -f api
```

### 4. Cómo parar y limpiar todo
Para detener de forma segura todos los contenedores y remover los volúmenes de datos creados en runtime:

```bash
docker compose down -v
```

---

## Detalles Técnicos y Optimizaciones Aplicadas

### 1. Imagen Multi-stage Liviana 
* **Base:** Utiliza `python:3.11-slim` como imagen base oficial.
* **Instalación con `uv`:** Durante la fase de construcción, se emplea el resolvedor `uv` para compilar un entorno virtual con las dependencias mínimas requeridas por FastAPI (`fastapi`, `uvicorn`, `duckdb`, `pydantic`).
* **Aislamiento:** La imagen de ejecución final no contiene herramientas de compilación ni dependencias innecesarias, logrando un tamaño de imagen de **~175MB**.
* **Volumen Montado en Runtime:** La imagen no incluye los archivos de datos (`.db`, `.parquet`, `.csv`). En su lugar, el directorio `data/` del anfitrión se monta dinámicamente en `/data` en los contenedores.

### 2. Formato de Logs JSON
Tanto los logs internos de la aplicación como los generados por el servidor web `Uvicorn` han sido interceptados y formateados como strings JSON válidos en `stdout`. Cada línea representa un objeto JSON independiente con la siguiente estructura:

```json
{"timestamp": "2026-06-01T02:15:30.123456", "level": "INFO", "message": "SQLite connection initialized successfully with WAL mode.", "logger": "api_db"}
```
