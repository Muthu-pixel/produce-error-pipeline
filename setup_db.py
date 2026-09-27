"""One-time setup: creates the rca_orders_demo database and its orders
tables (one healthy, one with a drifted column name, one with a data-quality
gap in a JSON metadata column), then seeds each with sample rows. Run once
before running main.py."""

import json
import random

import pyodbc

from config.db_config import SERVER, DATABASE

MASTER_CONNECTION_STRING = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={SERVER};"
    "DATABASE=master;"
    "Trusted_Connection=yes;"
)

# Sizing for the timeout scenario's row explosion (see create_and_seed_timeout_tables
# and src/pipeline/extract.py's extract_slow_join). Bump these up if the join doesn't
# reliably blow past extract.py's TIMEOUT_QUERY_SECONDS on your hardware.
TIMEOUT_CUSTOMERS = [f"region_cust_{i}" for i in range(4)]
TIMEOUT_ORDERS_PER_CUSTOMER = 1000
TIMEOUT_HISTORY_ROWS_PER_CUSTOMER = 4000


def create_database() -> None:
    conn = pyodbc.connect(MASTER_CONNECTION_STRING, autocommit=True)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sys.databases WHERE name = ?", DATABASE)
    if cursor.fetchone() is None:
        cursor.execute(f"CREATE DATABASE [{DATABASE}]")
    conn.close()
    print(f"Database '{DATABASE}' ready")


def create_and_seed_tables() -> None:
    from config.db_config import CONNECTION_STRING

    conn = pyodbc.connect(CONNECTION_STRING, autocommit=True)
    cursor = conn.cursor()

    cursor.execute("IF OBJECT_ID('dbo.orders_healthy', 'U') IS NOT NULL DROP TABLE dbo.orders_healthy")
    cursor.execute("""
        CREATE TABLE dbo.orders_healthy (
            order_id INT PRIMARY KEY,
            customer_id VARCHAR(20) NOT NULL,
            quantity INT NOT NULL,
            unit_price DECIMAL(10, 2) NOT NULL,
            order_date DATE NOT NULL
        )
    """)

    cursor.execute("IF OBJECT_ID('dbo.orders_drift', 'U') IS NOT NULL DROP TABLE dbo.orders_drift")
    cursor.execute("""
        CREATE TABLE dbo.orders_drift (
            order_id INT PRIMARY KEY,
            cust_id VARCHAR(20) NOT NULL,
            quantity INT NOT NULL,
            unit_price DECIMAL(10, 2) NOT NULL,
            order_date DATE NOT NULL
        )
    """)

    cursor.execute("IF OBJECT_ID('dbo.orders_dq', 'U') IS NOT NULL DROP TABLE dbo.orders_dq")
    cursor.execute("""
        CREATE TABLE dbo.orders_dq (
            order_id INT PRIMARY KEY,
            customer_id VARCHAR(20) NOT NULL,
            quantity INT NOT NULL,
            unit_price DECIMAL(10, 2) NOT NULL,
            order_date DATE NOT NULL,
            metadata NVARCHAR(MAX) NOT NULL
        )
    """)
    print("Tables created")

    rows = [
        (i, f"cust_{i % 5}", random.randint(1, 5), round(random.uniform(5, 50), 2), "2026-09-13")
        for i in range(1, 21)
    ]
    cursor.executemany(
        "INSERT INTO dbo.orders_healthy (order_id, customer_id, quantity, unit_price, order_date) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    cursor.executemany(
        "INSERT INTO dbo.orders_drift (order_id, cust_id, quantity, unit_price, order_date) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )

    # order_id 7's upstream record is missing "promo_code" -- a real data-quality gap
    # in one row, not a schema-wide rename. Every other row has it.
    dq_rows = [
        (
            order_id, customer_id, quantity, unit_price, order_date,
            json.dumps({"gift_wrap": False}) if order_id == 7 else json.dumps({"promo_code": "SAVE10", "gift_wrap": False}),
        )
        for order_id, customer_id, quantity, unit_price, order_date in rows
    ]
    cursor.executemany(
        "INSERT INTO dbo.orders_dq (order_id, customer_id, quantity, unit_price, order_date, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        dq_rows,
    )
    print(f"Seeded {len(rows)} rows into each table")
    conn.close()


def create_and_seed_timeout_tables() -> None:
    """orders_timeout + customer_region_history: a slowly-changing dimension
    table with many historical rows per customer, deliberately left
    unindexed on customer_id -- it was only ever meant to be queried with an
    effective-date filter. extract.py's extract_slow_join() "forgets" that
    filter (a real, common bug), so every order fans out against every
    history row for its customer -- a genuine row explosion, not a fabricated
    delay."""
    from config.db_config import CONNECTION_STRING

    conn = pyodbc.connect(CONNECTION_STRING, autocommit=True)
    cursor = conn.cursor()

    cursor.execute("IF OBJECT_ID('dbo.orders_timeout', 'U') IS NOT NULL DROP TABLE dbo.orders_timeout")
    cursor.execute("""
        CREATE TABLE dbo.orders_timeout (
            order_id INT PRIMARY KEY,
            customer_id VARCHAR(20) NOT NULL,
            quantity INT NOT NULL,
            unit_price DECIMAL(10, 2) NOT NULL,
            order_date DATE NOT NULL
        )
    """)

    cursor.execute("IF OBJECT_ID('dbo.customer_region_history', 'U') IS NOT NULL DROP TABLE dbo.customer_region_history")
    cursor.execute("""
        CREATE TABLE dbo.customer_region_history (
            history_id INT IDENTITY(1, 1) PRIMARY KEY,
            customer_id VARCHAR(20) NOT NULL,
            region VARCHAR(20) NOT NULL,
            effective_from DATE NOT NULL,
            effective_to DATE NOT NULL
        )
    """)
    print("Timeout scenario tables created")

    order_rows = [
        (
            i,
            TIMEOUT_CUSTOMERS[i % len(TIMEOUT_CUSTOMERS)],
            random.randint(1, 5),
            round(random.uniform(5, 50), 2),
            "2026-09-13",
        )
        for i in range(1, TIMEOUT_ORDERS_PER_CUSTOMER * len(TIMEOUT_CUSTOMERS) + 1)
    ]
    cursor.executemany(
        "INSERT INTO dbo.orders_timeout (order_id, customer_id, quantity, unit_price, order_date) "
        "VALUES (?, ?, ?, ?, ?)",
        order_rows,
    )

    history_rows = [
        (customer_id, f"region_{j % 10}", "2020-01-01", "2020-12-31")
        for customer_id in TIMEOUT_CUSTOMERS
        for j in range(TIMEOUT_HISTORY_ROWS_PER_CUSTOMER)
    ]
    cursor.executemany(
        "INSERT INTO dbo.customer_region_history (customer_id, region, effective_from, effective_to) "
        "VALUES (?, ?, ?, ?)",
        history_rows,
    )
    print(
        f"Seeded {len(order_rows)} orders and {len(history_rows)} region-history rows "
        f"({TIMEOUT_ORDERS_PER_CUSTOMER}/customer orders x {TIMEOUT_HISTORY_ROWS_PER_CUSTOMER}/customer "
        "history rows -- the join in extract_slow_join() fans every order out against "
        "every history row for its customer)"
    )
    conn.close()


def create_and_seed_malformed_dq_table() -> None:
    """orders_dq_malformed: same shape as orders_dq, but a different real
    defect -- one row's metadata isn't valid JSON at all (not just missing a
    key), so json.loads() raises a real JSONDecodeError. Tests whether the
    data_quality category generalizes past the one specific KeyError bug in
    orders_dq, rather than just pattern-matching that one exception."""
    from config.db_config import CONNECTION_STRING

    conn = pyodbc.connect(CONNECTION_STRING, autocommit=True)
    cursor = conn.cursor()

    cursor.execute("IF OBJECT_ID('dbo.orders_dq_malformed', 'U') IS NOT NULL DROP TABLE dbo.orders_dq_malformed")
    cursor.execute("""
        CREATE TABLE dbo.orders_dq_malformed (
            order_id INT PRIMARY KEY,
            customer_id VARCHAR(20) NOT NULL,
            quantity INT NOT NULL,
            unit_price DECIMAL(10, 2) NOT NULL,
            order_date DATE NOT NULL,
            metadata NVARCHAR(MAX) NOT NULL
        )
    """)
    print("Malformed-JSON data-quality table created")

    rows = [
        (i, f"cust_{i % 5}", random.randint(1, 5), round(random.uniform(5, 50), 2), "2026-09-13")
        for i in range(1, 21)
    ]
    # order_id 11's metadata is not valid JSON at all -- a corrupt payload,
    # not a missing key. Every other row is well-formed.
    malformed_rows = [
        (
            order_id, customer_id, quantity, unit_price, order_date,
            "{not valid json" if order_id == 11 else json.dumps({"promo_code": "SAVE10", "gift_wrap": False}),
        )
        for order_id, customer_id, quantity, unit_price, order_date in rows
    ]
    cursor.executemany(
        "INSERT INTO dbo.orders_dq_malformed (order_id, customer_id, quantity, unit_price, order_date, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        malformed_rows,
    )
    print(f"Seeded {len(malformed_rows)} rows (order_id 11 has invalid JSON metadata)")
    conn.close()


if __name__ == "__main__":
    create_database()
    create_and_seed_tables()
    create_and_seed_timeout_tables()
    create_and_seed_malformed_dq_table()
