import duckdb

def execute_query(query, path):
    # Use path directly in read_parquet
    sql = query.replace("TABLE", f"read_parquet('{path}')")
    return duckdb.query(sql).to_df()

def q1(path):
    query = """
    SELECT country_code, COUNT(*) as count
    FROM TABLE
    GROUP BY country_code
    ORDER BY count DESC
    """
    return execute_query(query, path)

def q2(path):
    query = """
    SELECT category, AVG(amount) as mean, MIN(amount) as min, MAX(amount) as max
    FROM TABLE
    GROUP BY category
    """
    return execute_query(query, path)

def q3(path):
    query = """
    SELECT user_id, SUM(amount) as sum, COUNT(*) as count
    FROM TABLE
    GROUP BY user_id
    ORDER BY sum DESC
    LIMIT 10
    """
    return execute_query(query, path)

def q4(path):
    query = """
    SELECT HOUR(timestamp) as hour, COUNT(*) as count
    FROM TABLE
    WHERE status = 'failed'
    GROUP BY hour
    ORDER BY hour
    """
    return execute_query(query, path)

def q5(path):
    query = """
    SELECT *
    FROM TABLE
    WHERE amount > 500
      AND country_code IN ('MX', 'CO')
      AND timestamp >= (SELECT MAX(timestamp) FROM TABLE) - INTERVAL 30 DAY
    """
    return execute_query(query, path)

def q6(path):
    query = """
    WITH stats AS (
        SELECT country_code, category, COUNT(*) as count, AVG(amount) as avg_amount
        FROM TABLE
        GROUP BY country_code, category
    ),
    ranked AS (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY country_code ORDER BY count DESC) as rn
        FROM stats
    )
    SELECT country_code, category, count, avg_amount
    FROM ranked
    WHERE rn = 1
    """
    return execute_query(query, path)

def q7(path):
    query = """
    SELECT user_id, COUNT(*) as failed_count
    FROM TABLE
    WHERE status = 'failed'
    GROUP BY user_id
    HAVING failed_count > 5
    """
    return execute_query(query, path)

def q8(path):
    query = """
    SELECT CAST(timestamp AS DATE) as date, category, AVG(amount) as avg_amount
    FROM TABLE
    GROUP BY date, category
    """
    return execute_query(query, path)

def get_explain_analyze(q_id, path):
    queries = {
        'Q3': """
            SELECT user_id, SUM(amount) as sum, COUNT(*) as count
            FROM TABLE
            GROUP BY user_id
            ORDER BY sum DESC
            LIMIT 10
        """,
        'Q5': """
            SELECT *
            FROM TABLE
            WHERE amount > 500
              AND country_code IN ('MX', 'CO')
              AND timestamp >= (SELECT MAX(timestamp) FROM TABLE) - INTERVAL 30 DAY
        """,
        'Q6': """
            WITH stats AS (
                SELECT country_code, category, COUNT(*) as count, AVG(amount) as avg_amount
                FROM TABLE
                GROUP BY country_code, category
            ),
            ranked AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY country_code ORDER BY count DESC) as rn
                FROM stats
            )
            SELECT country_code, category, count, avg_amount
            FROM ranked
            WHERE rn = 1
        """
    }
    sql = f"PRAGMA enable_profiling; EXPLAIN ANALYZE {queries[q_id].replace('TABLE', f'read_parquet(\'{path}\')')}"
    res = duckdb.query(sql).fetchone()
    return res[1] if res else "No explain available"
