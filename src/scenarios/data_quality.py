from src.pipeline.enrich import enrich_orders
from src.pipeline.extract import extract
from src.pipeline.transform import transform
from src.pipeline.validate import validate


def run() -> None:
    """1 of 20 rows' metadata JSON is missing promo_code; enrich crashes with a real KeyError."""
    orders = extract("data_quality")
    orders = validate(orders)
    transform(orders)
    enrich_orders(orders)
