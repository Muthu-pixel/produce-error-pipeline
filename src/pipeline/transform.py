import logging

logger = logging.getLogger("orders_etl")


def transform(orders: list[dict]) -> dict:
    logger.info("Transform stage started")
    for order in orders:
        order["revenue"] = order["quantity"] * order["unit_price"]

    revenue_by_customer = compute_customer_revenue(orders)

    logger.info(f"Computed revenue for {len(revenue_by_customer)} customers")
    logger.info("Transform stage completed")
    return revenue_by_customer


def compute_customer_revenue(orders: list[dict]) -> dict:
    revenue_by_customer: dict = {}
    for order in orders:
        customer = order["customer_id"]
        revenue_by_customer[customer] = revenue_by_customer.get(customer, 0) + order["revenue"]
    return revenue_by_customer
