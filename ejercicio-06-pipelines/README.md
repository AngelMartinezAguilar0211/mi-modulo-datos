# Ejercicio 6: El Pipeline de Datos (ETL)

Este directorio contiene la implementación de un pipeline de **Extracción, Transformación y Carga (ETL)** para ingestar, validar y persistir transacciones financieras de manera **idempotente** y **transaccional**.

Aproximadamente el tiempo de desarrollo de este ejercicio fue de 5 horas.

El pipeline está completamente modularizado y gestionado a través de **`uv`**.

---

## Arquitectura y Diseño de Capas

El sistema se ha diseñado bajo los principios de separación estricta de responsabilidades:

1. **`data_source.py` (Fuente):** Simula flujos de entrada mediante la generación de transacciones. Para poner a prueba la resiliencia del pipeline, se generan un porcentaje de anomalías sintácticas y de negocio basadas en una tasa de error ajustable.
2. **`extract.py` (Extracción y Normalización):** Capa encargada de normalizar tipos y formatos. Estandariza timestamps a cadenas ISO 8601 UTC, normaliza códigos de país a mayúsculas y redondea montos a exactamente 2 decimales. No realiza validaciones de negocio.
3. **`transform.py` (Transformación y Negocio):** Evalúa los registros normalizados contra las reglas estrictas del dominio financiero. Los registros que violan al menos una regla son redirigidos a la carpeta `quarantine/` en formato JSONLines. Los válidos prosiguen el flujo.
4. **`load.py` (Carga Transaccional):** Capa de persistencia en SQLite que utiliza transacciones explícitas y garantiza que el pipeline sea idempotente.
5. **`pipeline.py` (Orquestador):** El punto de entrada central. Coordina el flujo completo, mide latencias y guarda el reporte estructurado de métricas en `results/`. Ademas, lo imprime en terminal para visualizarlo de forma sencilla.

---

## Guía de Ejecución

### 1. Preparar el Entorno
Primero se debe de sincronizar las dependencias del proyecto:
```bash
uv sync
```

### 2. Ejecutar el Pipeline Completo
El orquestador `pipeline.py` ejecutará todas las fases de manera unificada y presentará un **dashboard** en la consola:

```bash
uv run python pipeline.py --batch-size 500 --error-rate 0.15
```

#### Parámetros Aceptados:
* `--batch-size`: Cantidad de transacciones a procesar (Número entero. Por defecto, aleatorio entre 100 y 1000).
* `--error-rate`: Probabilidad de inyectar errores en cada registro generado (Flotante entre `0.0` y `1.0`. Por defecto `0.1`).
* `--db`: Ruta personalizada de la base de datos SQLite (Por defecto: `../data/transactions.db`).
* `--quarantine`: Carpeta para la salida de registros con error (Por defecto: `./quarantine`).
* `--results`: Carpeta para los reportes JSON de performance (Por defecto: `./results`).

---

## 🧪 Pruebas Automatizadas

La suite de pruebas con `pytest` cubre principalmente los cuatro casos críticos detallados en el plan de implementación:
1. **Happy Path:** Procesamiento limpio y carga sin anomalías.
2. **Validaciones de Negocio y Cuarentena:** Detección de tipos de error exactos y formateo de quarantined files.
3. **Idempotencia:** Doble ejecución con el mismo lote verificando métricas de duplicados sin inyecciones adicionales.
4. **Atomicidad Transaccional:** Simulación de fallo en base de datos en medio del lote para comprobar que el rollback es de 100%.

Para ejecutar los tests se usa el comando (dentro de la carpeta `ejercicio-06-pipelines`):
```bash
uv run pytest tests/test_pipeline.py -v
```

---

## Formato del Reporte JSON (`results/`)

Cada ejecución exitosa genera un archivo autodescriptivo en `results/run_YYYYMMDD_HHMMSS.json` con la siguiente estructura:

```json
{
    "run_id": "20260528_214530",
    "timestamp": "2026-05-28T21:45:30.123456+00:00",
    "filas_extraidas": 500,
    "filas_validas": 450,
    "filas_rechazadas": 50,
    "filas_rechazadas_por_tipo_de_error": {
        "amount_out_of_range": 10,
        "invalid_category": 12,
        "invalid_country": 8,
        "future_timestamp": 12,
        "invalid_uuid": 8,
        "missing_fields": 0
    },
    "filas_insertadas": 420,
    "filas_duplicadas": 30,
    "tiempo_total": 0.045612
}
```

### Explicación de Métricas:
* `filas_extraidas`: Total de transacciones tomadas de la fuente cruda.
* `filas_validas`: Cantidad de filas que cumplieron al 100% las reglas de negocio.
* `filas_rechazadas`: Cantidad de filas con errores que fueron derivadas a cuarentena.
* `filas_rechazadas_por_tipo_de_error`: Desglose exacto de anomalías encontradas por categoría técnica.
* `filas_insertadas`: Transacciones nuevas ingresadas a la base SQLite.
* `filas_duplicadas`: Transacciones válidas que fueron ignoradas por la base de datos porque su `transaction_id` ya existía previamente en SQLite.
* `tiempo_total`: Tiempo total medido de la corrida en segundos.

---

## Formato de la Cuarentena (`quarantine/`)

Las transacciones rechazadas se almacenan en `quarantine/YYYY-MM-DD.jsonl`. Cada línea es un objeto JSON autónomo que contiene el registro original normalizado, los motivos de rechazo detallados en forma de lista y el timestamp en el que fue procesado:

```json
{
  "transaction": {
    "transaction_id": "not-a-uuid",
    "timestamp": "2026-05-28T21:45:30Z",
    "user_id": 1500,
    "merchant_id": 850,
    "amount": -50.00,
    "category": "Gambling",
    "country_code": "MX",
    "status": "completed"
  },
  "rejection_reasons": ["amount_out_of_range", "invalid_category", "invalid_uuid"],
  "quarantined_at": "2026-05-28T21:45:30.456789+00:00"
}
```
