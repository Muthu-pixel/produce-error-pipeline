import logging

logger = logging.getLogger("orders_etl")


def validate(orders: list[dict]) -> list[dict]:
    logger.info("Validation stage started")
    if not orders:
        raise ValueError("No rows extracted")
    logger.info("Validation stage completed")
    return orders
