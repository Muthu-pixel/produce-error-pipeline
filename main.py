import argparse
import logging
from datetime import datetime
from pathlib import Path

from extract import extract, SCENARIO_TABLES
from validate import validate
from transform import transform
from enrich import enrich_orders

REPO_NAME = Path(__file__).resolve().parent.name
LOG_DIR = Path(__file__).resolve().parent.parent / "RCA_LOGS"
LOG_DIR.mkdir(exist_ok=True)


def setup_logging() -> None:
    # microsecond precision -- two scenarios run back-to-back can otherwise land in the
    # same second and get merged into one file, since FileHandler defaults to append mode
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_path = LOG_DIR / f"{REPO_NAME}_{timestamp}.log"
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(funcName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run(scenario: str) -> None:
    logger = logging.getLogger("orders_etl")
    logger.info("Starting pipeline: orders_etl")
    logger.info(f"Source file: {Path(__file__).resolve()}")
    logger.info(f"Scenario: {scenario}")
    try:
        orders = extract(scenario)
        orders = validate(orders)
        transform(orders)
        # only orders_dq has a metadata column to enrich -- other scenarios don't
        # go through this stage at all, same as a real pipeline whose downstream
        # steps differ by source.
        if scenario == "data_quality":
            enrich_orders(orders)
        logger.info("Pipeline run ended with status: SUCCESS")
    except Exception:
        logger.exception("Pipeline stage failed")
        logger.error("Pipeline run ended with status: FAILED")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=sorted(SCENARIO_TABLES))
    args = parser.parse_args()

    setup_logging()
    run(args.scenario)
