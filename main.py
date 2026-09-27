import argparse
import logging
from datetime import datetime
from pathlib import Path

from src.scenarios import code_bug, data_quality, data_quality_malformed, healthy, schema_drift, timeout

REPO_NAME = Path(__file__).resolve().parent.name
LOG_DIR = Path(__file__).resolve().parent.parent / "RCA_LOGS"
LOG_DIR.mkdir(exist_ok=True)

# One function per scenario -- each is fully self-contained (it wires whichever
# pipeline stages it needs). Adding a new scenario means writing a new module
# in src/scenarios/ and registering its run() here; no existing entry changes.
SCENARIOS = {
    "healthy": healthy.run,
    "schema_drift": schema_drift.run,
    "data_quality": data_quality.run,
    "data_quality_malformed": data_quality_malformed.run,
    "timeout": timeout.run,
    "code_bug": code_bug.run,
}


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
        # without this, only the first setup_logging() call in a process actually
        # attaches a file handler -- needed so run_all() gets one log file per scenario
        force=True,
    )


def run(scenario: str) -> None:
    logger = logging.getLogger("orders_etl")
    logger.info("Starting pipeline: orders_etl")
    logger.info(f"Source file: {Path(__file__).resolve()}")
    logger.info(f"Scenario: {scenario}")
    try:
        SCENARIOS[scenario]()
        logger.info("Pipeline run ended with status: SUCCESS")
    except Exception:
        logger.exception("Pipeline stage failed")
        logger.error("Pipeline run ended with status: FAILED")
        raise


def run_all() -> None:
    # each scenario gets its own log file and its own try/except -- one scenario's
    # (expected) failure must not stop the rest from running
    for scenario in sorted(SCENARIOS):
        setup_logging()
        try:
            run(scenario)
        except Exception:
            continue


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "scenario",
        nargs="?",
        default=None,
        choices=sorted(SCENARIOS),
        help="Scenario to run. Omit to run every scenario one by one.",
    )
    args = parser.parse_args()

    if args.scenario is None:
        run_all()
    else:
        setup_logging()
        run(args.scenario)
