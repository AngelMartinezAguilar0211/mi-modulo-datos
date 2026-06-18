# Documento de Decisiones Técnicas — Ejercicio 8: Proyecto Final

## 1. Tecnologías Elegidas por Capa

### Capa de API: FastAPI sobre Django REST Framework

Para la capa de API elegí FastAPI en lugar de Django REST Framework. La razón principal es el rendimiento medido durante los ejercicios anteriores. En el Ejercicio 4 construí la API original con FastAPI y se lograron tiempos de respuesta consistentemente por debajo de 200 milisegundos en todos los endpoints analíticos, incluso sobre un dataset de un millón de transacciones. En el Ejercicio 5, al reconstruir los mismos endpoints con Django REST Framework, observé que la latencia promedio era mayor debido a la sobrecarga del middleware de Django, el sistema de autenticación por token, y la serialización adicional que DRF impone sobre cada respuesta.

FastAPI también permite integrar DuckDB directamente como motor analítico sin fricción. No hay un ORM de por medio que me obligue a pasar por una capa de abstracción innecesaria para las queries OLAP. Puedo ejecutar SQL directo sobre el Parquet y devolver los resultados en milisegundos. Django REST Framework, en cambio, está diseñado para trabajar con su ORM, y aunque es posible ejecutar queries crudas, la integración no es tan natural.

La tercera razón es la simplicidad operativa. FastAPI con Uvicorn es un solo proceso que puedo contenerizar en una imagen de menos de 200 megabytes. Django requiere más configuración: settings, middleware, apps instaladas, migraciones. Para un sistema de monitoreo donde el rendimiento es crítico y la API es relativamente directa (8 endpoints sin vistas HTML), FastAPI es la herramienta correcta.

### Capa OLTP (Transaccional): SQLite con WAL

Para las operaciones transaccionales — consultas por usuario, inserción de batches, detección de anomalías — uso SQLite en modo Write-Ahead Logging (WAL). En el Ejercicio 3 se demostró que SQLite con los índices correctos (compuestos sobre user_id + timestamp, y sobre status + timestamp para anomalías) responde en menos de 50 milisegundos para consultas puntuales sobre un millón de filas.

La ventaja operativa de SQLite es que no requiere un servidor de base de datos separado. El archivo .db se monta como volumen en Docker y es accesible directamente desde el proceso de la API. Esto simplifica la configuración de contenedores y elimina la necesidad de gestionar conexiones de red, credenciales de base de datos, y un contenedor adicional para PostgreSQL o MySQL.

### Capa OLAP (Analítica): DuckDB In-Memory sobre Parquet

Para las queries analíticas — resúmenes globales, top merchants, breakdowns por país y categoría — se usa DuckDB con una vista in-memory sobre el archivo Parquet. En el Ejercicio 4 se midio que DuckDB responde en menos de 200 milisegundos para aggregaciones completas sobre el millón de filas, mientras que la misma query en SQLite tardaba más de un segundo.

DuckDB opera como un motor columnar embebido que lee directamente del Parquet sin necesidad de cargar los datos en memoria manualmente. Esto permite mantener los datos analíticos separados de los datos transaccionales, cada motor optimizado para su caso de uso.

### Capa de Pipeline: Stdlib de Python (csv, sqlite3)

El pipeline de ingesta usa únicamente la biblioteca estándar de Python para leer CSV, validar datos, y escribir en SQLite. No se usa pandas ni polars dentro del pipeline. La razón es que las dependencias adicionales incrementan el tamaño de la imagen Docker significativamente (pandas añade más de 100 megabytes), y para el caso de uso de validar e insertar filas una por una, el módulo csv de la stdlib es suficiente y más eficiente en memoria.

---

## 2. Compromisos y Consecuencias

### SQLite como Single-Writer vs PostgreSQL Multi-Writer

SQLite tiene una limitación: solo un proceso puede escribir a la vez. En este sistema, las escrituras ocurren en dos momentos: durante la ingesta del pipeline y durante los batch inserts de la API. Ambos pasan por la misma conexión SQLite del proceso FastAPI, así que no hay conflicto de concurrencia.

La consecuencia es que si el sistema necesitara escalar a múltiples workers de Uvicorn o múltiples instancias de la API, SQLite se convertiría en un cuello de botella. La migración natural sería a PostgreSQL con connection pooling.

### DuckDB In-Memory vs Persistente

La vista de DuckDB se crea in-memory al inicio de la API. Esto significa que cada vez que el contenedor se reinicia, DuckDB relee el Parquet. El costo es un arranque en frío de aproximadamente 2 a 3 segundos, pero a cambio se obtienen queries analíticas extremadamente rápidas sin persistir un segundo archivo de datos.

La consecuencia es que las transacciones insertadas via batch o pipeline no aparecen en los endpoints analíticos hasta que se regenere el Parquet. Para un sistema de monitoreo donde los datos analíticos pueden tener un retraso de minutos, esto es aceptable.

### Validación Doble: Pydantic en API + Pipeline Transform

Los datos pasan por validación Pydantic en el endpoint POST /transactions/batch y por validación de reglas de negocio en el pipeline de ingesta. Esto significa que hay dos capas de validación con reglas similares. El costo es duplicación de lógica, pero la ganancia es que cada punto de entrada tiene su propia garantía de integridad sin depender del otro.

---

## 3. Escalabilidad a 100 Millones de Filas

Con 100 millones de filas, tres componentes necesitarían cambiar:

**Base de datos transaccional:** SQLite no soportaría el volumen de escrituras concurrentes ni el tamaño del archivo. La migración sería a PostgreSQL con particionamiento por fecha (timestamp) y connection pooling con pgbouncer.

**Motor analítico:** DuckDB in-memory con 100 millones de filas consumiría más de 8 gigabytes de RAM. La alternativa sería DuckDB leyendo particiones de Parquet por mes, o migrar a ClickHouse para queries distribuidas.

**Pipeline de ingesta:** Con volúmenes de 100 millones, el pipeline secuencial sería demasiado lento. La solución sería implementar workers paralelos con Celery o un DAG de Apache Airflow que procese batches de CSV en paralelo, cada worker insertando en una partición diferente.

**API:** FastAPI con un solo worker no soportaría la carga. Se necesitarían múltiples workers de Gunicorn detrás de un balanceador de carga, o despliegue en Kubernetes con autoescalado horizontal.

---

## 4. Monitoreo en Producción

### Métricas que Monitorearía

El endpoint /health ya expone métricas clave: uptime, conexiones activas, hit rate del cache, y estado de conectividad de SQLite y DuckDB. En producción agregaría:

- **Latencia P95 por endpoint:** Si el percentil 95 de /analytics/summary supera 500ms, hay un problema de rendimiento.
- **Tasa de errores 5xx:** Un incremento súbito indica un fallo en las conexiones de base de datos o en el procesamiento de queries.
- **Pipeline quarantine rate:** Si más del 20% de las filas de un CSV son rechazadas, la fuente de datos tiene un problema de calidad.
- **Anomaly count trend:** Un aumento repentino en el número de usuarios flaggeados por anomalías podría indicar un ataque de fraude o un bug en el procesamiento de pagos.

### Cómo Detectaría Problemas

Configuraría alertas en Grafana sobre los datos del endpoint /health, consultado cada 30 segundos por Prometheus. Las reglas de alerta serían:

1. **Health degraded por más de 2 minutos:** Alerta crítica — alguna base de datos no responde.
2. **Cache hit rate por debajo de 50%:** Alerta de warning — posible memory pressure o TTL mal configurado.
3. **Pipeline insert rate de 0 por más de 1 hora:** Alerta informativa — verificar que la fuente de datos está activa.

