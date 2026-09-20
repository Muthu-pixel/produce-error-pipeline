"""One-time setup: creates the rca_orders_demo database and its orders
tables (one healthy, one with a drifted column name, one with a data-quality
gap in a JSON metadata column), then seeds each with sample rows. Run once
before running main.py."""

import json
import random

import pyodbc

from db_config import SERVER, DATABASE

MASTER_CONNECTION_STRING = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={SERVER};"
    "DATABASE=master;"
    "Trusted_Connection=yes;"
)


def create_database() -> None:
    conn = pyodbc.connect(MASTER_CONNECTION_STRING, autocommit=True)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sys.databases WHERE name = ?", DATABASE)
    if cursor.fetchone() is None:
        cursor.execute(f"CREATE DATABASE [{DATABASE}]")
    conn.close()
    print(f"Database '{DATABASE}' ready")


def create_and_seed_tables() -> None:
    from db_config import CONNECTION_STRING

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


if __name__ == "__main__":
    create_database()
    create_and_seed_tables()
