import logging

import pyodbc

from db_config import CONNECTION_STRING

logger = logging.getLogger("orders_etl")

# Healthy scenario reads orders_healthy (has customer_id); schema_drift reads
# orders_drift (upstream renamed the column to cust_id) -- a real DB-level
# schema mismatch, not a fabricated one. data_quality reads orders_dq, where
# the schema is fine but one row's metadata JSON is missing a key the other
# 19 rows all have -- a real per-record data gap, not a schema-wide issue.
SCENARIO_TABLES = {
    "healthy": "orders_healthy",
    "schema_drift": "orders_drift",
    "data_quality": "orders_dq",
}


def extract(scenario: str) -> list[dict]:
    logger.info("Extract stage started")
    table = SCENARIO_TABLES[scenario]
    logger.info(f"Querying dbo.{table} from SQL Server")

    conn = pyodbc.connect(CONNECTION_STRING, timeout=5)
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM dbo.{table}")
    columns = [col[0] for col in cursor.description]
    orders = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()

    logger.info(f"Extracted {len(orders)} rows total")
    logger.info(f"Columns found: {columns}")
    logger.info("Extract stage completed")
    return orders
