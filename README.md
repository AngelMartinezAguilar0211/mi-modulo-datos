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

---

## Ejercicio 3: La Capa Transaccional

Este ejercicio se enfoca en implementar una capa de almacenamiento transaccional utilizando **SQLite**. El objetivo es diseñar un esquema optimizado con los índices correctos (B-Tree) para resolver 5 patrones de acceso específicos con latencias muy bajas (SLAs < 50ms), y comparar este rendimiento analítico contra DuckDB.

### Guía de Ejecución y Resultados

Toda la documentación técnica (como la justificación del esquema), las instrucciones detalladas para regenerar la base de datos, los comandos para ejecutar los benchmarks y el análisis detallado de los resultados (SQLite vs DuckDB) se encuentran en el README interno del ejercicio:

👉 [**ejercicio-03-sqlite/README.md**](./ejercicio-03-sqlite/README.md)

---

## Ejercicio 4: El Sistema Completo (API Serving Layer)

Este ejercicio se centra en integrar los componentes desarrollados previamente para construir una API REST de alto rendimiento utilizando **FastAPI**. El sistema implementa una **arquitectura híbrida** optimizada: utiliza **SQLite** (OLTP) para operaciones transaccionales de lectura y escritura de baja latencia, y **DuckDB** (OLAP) para agregaciones y consultas analíticas masivas sobre un millón de registros. Adicionalmente, cuenta con una capa de **caché hilo-segura** en memoria.

### Guía de Ejecución y Resultados

Toda la documentación técnica (incluyendo el Registro de Decisiones de Arquitectura - ADR), las instrucciones paso a paso para levantar el servidor y ejecutar las pruebas de validación automatizadas, así como el reporte detallado de latencias (Cold vs. Warm caché) y la justificación del cumplimiento de SLAs, se encuentran en el README interno del ejercicio:

👉 [**ejercicio-04-sistema/README.md**](./ejercicio-04-sistema/README.md)

---

## Ejercicio 5: El Backend con Estructura (Django + DRF)

Este ejercicio consiste en reconstruir el backend del Ejercicio 4 utilizando **Django** y **Django REST Framework (DRF)**. Migrando de la flexibilidad de FastAPI a un framework más estructurado y convencional, el sistema conserva su **arquitectura híbrida** (SQLite para OLTP con índices del E3 y DuckDB para OLAP), incorpora **TokenAuthentication** para accesos protegidos, ofrece un panel de administración completo para gestionar transacciones, y cuenta con un comando para la ingesta de datos del Parquet en chunks.

### Guía de Ejecución y Resultados

Toda la documentación técnica, las instrucciones paso a paso para levantar el servidor con `uv`, migrar y poblar la base de datos de 1M de registros libre de advertencias, generar tokens de acceso y correr la suite de validación automatizada con `pytest`, se encuentran en el README interno del ejercicio:

👉 [**ejercicio-05-django/README.md**](./ejercicio-05-django/README.md)

---

## Ejercicio 6: El Pipeline de Datos (ETL)

Este ejercicio consiste en construir un pipeline ETL (Extract, Transform, Load) robusto, modular, transaccional e idempotente para ingestar flujos incrementales de transacciones financieras. El sistema simula la llegada de flujos con fallos mediante un inyector probabilístico de errores, normaliza tipos y formatos a estándares internacionales en la capa de extracción, y valida rigurosamente las transacciones contra las reglas del dominio de negocio en la capa de transformación. Los registros que fallan las validaciones son desviados de forma automatizada a una carpeta de cuarentena en formato JSONLines (`.jsonl`), mientras que los válidos son cargados atómicamente en la base de datos SQLite en un único bloque de transacción explícito. Además, la persistencia integra el Covering Index compuesto optimizado a partir del feedback del E03.

### Guía de Ejecución y Resultados

Toda la documentación técnica del diseño del pipeline, el desglose de métricas por corrida de ingesta en reportes JSON, comandos exactos para ejecutar la orquestación y las pruebas unitarias y de integración desarrolladas con `pytest`, se encuentran en el README interno de este ejercicio:

👉 [**ejercicio-06-pipelines/README.md**](./ejercicio-06-pipelines/README.md)

---

## Ejercicio 7: De tu Máquina al Mundo (Contenerización con Docker)

Este ejercicio implementa la contenerización completa de la API REST transaccional y analítica (basada en **FastAPI**, **SQLite** y **DuckDB**). El sistema define la infraestructura como código usando **Docker Compose**, orquestando un contenedor efímero (`setup`) para la creación e ingesta eficiente de la base de datos de 1M de registros a partir del Parquet, y un contenedor de producción (`api`) para servir el framework web, el cual inicia únicamente tras la finalización exitosa del setup. La arquitectura incorpora un health check automático cada 30 segundos, logs estructurados en formato JSON dirigidos a `stdout`, y una gestión de rutas y configuraciones a través de variables de entorno, manteniendo la imagen de ejecución por debajo de los 300MB.

### Guía de Ejecución y Resultados

Toda la documentación técnica de infraestructura, la justificación de pesos de imágenes, el direccionamiento de variables de entorno y los comandos exactos de ciclo de vida (levantar, inspeccionar logs, limpiar volúmenes) se encuentran en el README interno del ejercicio:

👉 [**ejercicio-07-contenedores/README.md**](./ejercicio-07-contenedores/README.md)


