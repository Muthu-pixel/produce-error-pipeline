from src.pipeline.enrich import enrich_orders
from src.pipeline.extract import extract
from src.pipeline.transform import transform
from src.pipeline.validate import validate


def run() -> None:
    """Same data_quality category as `data_quality`, but a different real
    defect: one row's metadata isn't valid JSON at all (not just missing a
    key), so json.loads() raises a real JSONDecodeError instead of a KeyError."""
    orders = extract("data_quality_malformed")
    orders = validate(orders)
    transform(orders)
    enrich_orders(orders)
