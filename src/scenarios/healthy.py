from src.pipeline.extract import extract
from src.pipeline.transform import transform
from src.pipeline.validate import validate


def run() -> None:
    """Runs the pipeline against clean data. No failure."""
    orders = extract("healthy")
    orders = validate(orders)
    transform(orders)
