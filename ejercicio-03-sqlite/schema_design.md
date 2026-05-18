# Justificación del Diseño del Esquema - Ejercicio 3

Este documento explica las decisiones técnicas tomadas para el esquema de SQLite y la estrategia de índices para cumplir con los SLAs de rendimiento de la capa transaccional.

## Estructura de la Tabla

La tabla `transactions` sigue el esquema definido en el Ejercicio 1. Utilizamos los tipos estándar de SQLite:
- `TEXT` para UUIDs y categorías.
- `DATETIME` para marcas de tiempo.
- `INTEGER` para IDs.
- `REAL` para montos de punto flotante.

## Estrategia de Índices

### 1. Clave Primaria (Primary Key): `transaction_id`
- **Patrón que resuelve**: P1 (Búsqueda por ID exacto).
- **Justificación**: Usar `transaction_id` como `PRIMARY KEY` crea automáticamente un índice B-Tree único. Dado que los UUIDs son únicos y buscamos coincidencias exactas, esto proporciona un tiempo de búsqueda de $O(\log N)$.

### 2. Índice Compuesto: `idx_user_timestamp` (`user_id`, `timestamp DESC`)
- **Patrones que resuelve**: P2, P3, P4.
- **Justificación**: 
    - **P2**: Al tener un índice compuesto que comienza con `user_id`, SQLite puede saltar directamente a los registros del usuario. La parte `timestamp DESC` le permite recuperar los últimos 20 registros sin una operación de ordenamiento separada (Optimización Top-N).
    - **P3 y P4**: Las consultas de rango sobre `timestamp` para un `user_id` específico son extremadamente eficientes con este índice porque todos los registros relevantes se almacenan de manera contigua en el B-Tree. Esto asegura **< 50ms** incluso para usuarios con muchas transacciones.

### 3. Índice de Columna Única: `idx_country_code` (`country_code`)
- **Patrón que resuelve**: P5 (Filtrar por país y agrupar por usuario).
- **Justificación**: Este índice permite a SQLite filtrar rápidamente las filas por `country_code`. Aunque la agrupación por `user_id` aún requiere algo de procesamiento, reducir el espacio de búsqueda a un solo país mejora significativamente el rendimiento.

## Consideraciones de Rendimiento

- **Modo WAL**: Habilitaremos Write-Ahead Logging (WAL) durante el benchmark para permitir lecturas concurrentes y mejorar el rendimiento de escritura.
- **Transacciones Explícitas**: La ingesta utiliza bloques de transacciones grandes para minimizar la sobrecarga de los commits atómicos al sistema de archivos.
- **Sobrecarga de Índices**: Aunque los índices aceleran las lecturas, ralentizan las escrituras. Sin embargo, dado el requisito de 1 millón de registros y el límite de ingesta de 3 minutos, los índices elegidos equilibrados para cumplir tanto con los SLAs de lectura como con las restricciones de escritura.
