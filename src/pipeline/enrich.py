import json
import logging

logger = logging.getLogger("orders_etl")


def parse_promo_code(metadata: dict) -> str:
    return metadata["promo_code"]


def enrich_orders(orders: list[dict]) -> list[dict]:
    logger.info("Enrich stage started")
    for order in orders:
        metadata = json.loads(order["metadata"])
        order["promo_code"] = parse_promo_code(metadata)
    logger.info(f"Enriched {len(orders)} orders with promo_code")
    logger.info("Enrich stage completed")
    return orders
