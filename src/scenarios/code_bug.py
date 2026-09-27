from src.pipeline.extract import extract
from src.pipeline.report import compute_top_customer_share
from src.pipeline.transform import transform
from src.pipeline.validate import validate


def run() -> None:
    """Reads the same healthy data as the `healthy` scenario -- schema and data
    are both fine. The bug is purely in the code: compute_top_customer_share
    hardcodes an assumption that more than 5 customers exist, but orders_healthy
    only ever has 5, so excluding the top 5 leaves nothing to average -- a real
    ZeroDivisionError from a wrong assumption, not from bad data or schema."""
    orders = extract("healthy")
    orders = validate(orders)
    revenue_by_customer = transform(orders)
    compute_top_customer_share(revenue_by_customer, top_n=5)
