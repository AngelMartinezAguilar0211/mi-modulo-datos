# Ejercicio 5: El Backend con Estructura (Django + DRF)

Este directorio contiene una reconstrucción de la API del Ejercicio 4 utilizando **Django** y **Django REST Framework (DRF)**.

Mantiene la compatibilidad exacta con los 6 endpoints definidos previamente, integrando la seguridad de `TokenAuthentication`, réplica exacta de índices del E3 y control de errores en formato HTTP 422 para validaciones.

---

## Estructura del Proyecto

- `config/`: Configuración principal de Django (`settings.py`, `urls.py`).
- `transactions/`: Aplicación principal de transacciones.
  - `models.py`: Modelo `Transaction` con `Meta.indexes` replicando los índices del E3.
  - `serializers.py`: Serializadores de DRF con validaciones exhaustivas de negocio.
  - `views.py`: Vistas optimizadas para endpoints OLTP (ORM) y OLAP (DuckDB).
  - `cache.py`: Componente de caché thread-safe en memoria (`InMemoryCache`).
  - `management/commands/load_transactions.py`: Ingestor de datos masivo ultraeficiente en chunks.
- `tests/`: Suite de pruebas automatizadas con `pytest`.

---

## Configuración y Puesta en Marcha

Se debe de entrar en la carpeta especifica del ejercicio para montar el sistema (`ejercicio-05-django/`):

### 1. Inicializar la Base de Datos y Aplicar Migraciones
Primeramente se debe estar seguro de tener las bibliotecas al igual que el resto de los ejercicios:

```bash 
uv sync
```

Seguidamente se debe de aplicar las migraciones para estructurar las tablas administrativas y transaccionales en SQLite:  
```bash
uv run python manage.py makemigrations
uv run python manage.py migrate
```

### 2. Ingestar el Dataset Parquet (1M de filas)
Se carga el conjunto de datos desde el archivo Parquet original usando la ingesta ORM:
```bash
uv run python manage.py load_transactions
```

### 3. Crear un Superusuario para el Administrador
Se crea un usuario administrador para acceder al panel de control de Django Admin:
```bash
uv run python manage.py createsuperuser
```

### 4. Generar o Obtener un Token de Autenticación
Se genera un token seguro para el usuario con el comando integrado de DRF:
```bash
uv run python manage.py drf_create_token <username>
```

### 5. Iniciar el Servidor de Desarrollo
Se levanta la API en modo local escuchando en `127.0.0.1:8000`:
```bash
uv run python manage.py runserver
```

---

## Ejecutar Pruebas Automatizadas

La suite de pruebas valida todos los endpoints (públicos y protegidos), latencia del SLA de salud, caché en memoria e inyección de lotes erróneos (HTTP 422).

Para correr los tests en tu entorno de desarrollo, se ejecuta:
```bash
uv run pytest tests/test_api.py -v
```

---

## Endpoints Disponibles

### Públicos
- `GET /health`: Estado detallado de las conexiones y métricas de rendimiento del caché.
- `GET /analytics/summary`: Agregados analíticos globales ejecutados mediante DuckDB directamente sobre Parquet.
- `GET /analytics/top-merchants?limit=N&country=CC`: Tabla de merchants líderes con filtros.

### Protegidos (Requieren `Authorization: Token <token_value>`)
- `GET /users/{user_id}/transactions?page=1&page_size=20`: Listado de transacciones paginado del ORM.
- `GET /users/{user_id}/stats`: Métricas transaccionales individuales del ORM.
- `POST /transactions/batch`: Carga segura y atómica en lote con deduplicación en memoria.

## NOTA:
Debido a que las URL estan protegidas con `TokenAuthentication`, es posible no poder ver su funcionamiento abriendolas directamente en el navegador. Estas se pueden visualizar mediante herramientas como "curl", "postman" o "Insomnia". Por ejemplo, para visualizar las transacciones del usuario con ID 1 se puede ejecutar el siguiente comando:

```bash
curl -X GET http://127.0.0.1:8000/users/1/transactions -H "Authorization: Token <token_value>"
```
