from src.pipeline.extract import extract_slow_join


def run() -> None:
    """A slowly-changing customer_region_history join is missing its
    effective-date predicate; every order fans out against every history row
    for its customer, producing a genuinely huge result set that blows past
    the query timeout with a real pyodbc timeout error."""
    extract_slow_join()
