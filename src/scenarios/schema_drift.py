from src.pipeline.extract import extract
from src.pipeline.transform import transform
from src.pipeline.validate import validate


def run() -> None:
    """Upstream renamed customer_id -> cust_id; transform crashes with a real KeyError."""
    orders = extract("schema_drift")
    orders = validate(orders)
    transform(orders)
