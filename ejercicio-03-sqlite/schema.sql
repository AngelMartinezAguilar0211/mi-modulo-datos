-- Schema for Exercise 3: Transactional Layer
-- This schema is optimized for the 5 access patterns (P1-P5)

DROP TABLE IF EXISTS transactions;

CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    user_id INTEGER NOT NULL,
    merchant_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    category TEXT NOT NULL,
    country_code TEXT NOT NULL,
    status TEXT NOT NULL
);

-- P1: Buscar una transacción por transacción_id exacto.
-- Handled by PRIMARY KEY (B-Tree index)

-- P2: Obtener las ultimas 20 transacciones de un user_id, ordenadas por timestamp.
-- P3: Todas las transacciones de un user_id en un rango de fechas dado.
-- P4: Suma de amount de un user_id en el ultimo mes.
-- Composite index on user_id and timestamp is ideal for these range/sort queries.
CREATE INDEX idx_user_timestamp ON transactions (user_id, timestamp DESC);

-- P5: Todos los user_id de un country_code con mas de N transacciones.
-- Index on country_code to quickly filter groups.
CREATE INDEX idx_country_code ON transactions (country_code);
