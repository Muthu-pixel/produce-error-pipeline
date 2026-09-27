import logging

import pyodbc

from config.db_config import CONNECTION_STRING

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
    # same category as data_quality, but a different real defect: one row's
    # metadata isn't valid JSON at all (not just missing a key) -- see setup_db.py
    "data_quality_malformed": "orders_dq_malformed",
}

# How long pyodbc will let extract_slow_join()'s query run before cancelling it
# and raising a real timeout error. Tune down/up (together with setup_db.py's
# TIMEOUT_* row counts) if the join doesn't reliably exceed this on your hardware.
TIMEOUT_QUERY_SECONDS = 3


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


def extract_slow_join() -> list[dict]:
    """Joins orders to customer_region_history but -- like a real, common
    bug -- omits the effective-date predicate that would normally narrow the
    match to one history row per order. Every order fans out against every
    history row for its customer, producing a genuinely huge result set that
    blows past TIMEOUT_QUERY_SECONDS and raises a real pyodbc timeout error."""
    logger.info("Extract stage started")
    query = (
        "SELECT o.order_id, o.customer_id, o.quantity, o.unit_price, o.order_date, h.region "
        "FROM dbo.orders_timeout o "
        "JOIN dbo.customer_region_history h ON o.customer_id = h.customer_id"
    )
    logger.info(f"Query timeout set to {TIMEOUT_QUERY_SECONDS}s")
    logger.info(f"Running query: {query}")

    conn = pyodbc.connect(CONNECTION_STRING, timeout=5)
    conn.timeout = TIMEOUT_QUERY_SECONDS
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        columns = [col[0] for col in cursor.description]
        orders = [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()

    logger.info(f"Extracted {len(orders)} rows total")
    logger.info("Extract stage completed")
    return orders
