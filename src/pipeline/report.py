import logging

logger = logging.getLogger("orders_etl")


def compute_top_customer_share(revenue_by_customer: dict, top_n: int) -> float:
    """Averages revenue among customers outside the top N by revenue. Assumes
    more than top_n customers exist -- wrong for orders_healthy, which only
    ever has 5, so excluding the top 5 leaves nothing to average."""
    logger.info("Report stage started")
    ranked = sorted(revenue_by_customer.values(), reverse=True)
    rest = ranked[top_n:]
    average_rest = sum(rest) / len(rest)
    logger.info(f"Average revenue among non-top-{top_n} customers: {average_rest}")
    logger.info("Report stage completed")
    return average_rest
