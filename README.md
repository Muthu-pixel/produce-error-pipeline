# sample-pipeline

A real-failure generator used as a runnable fixture for the
[ai-data-pipeline-rca-agent](../ai-data-pipeline-rca-agent) project. Not a
database-only tool: its job is to produce whichever *real* failure is
natural for a given root-cause category -- currently that means a small
SQL-Server-backed orders ETL (extract/validate/transform/enrich, each in its
own module), but future scenarios (a bad network call, a bad credential, a
resource limit) don't need to be DB-related at all. The one fixed contract:
every scenario must be a genuine failure from genuine execution (never a
hand-typed log line), and every run writes its own timestamped log to
`../RCA_LOGS/`, which is what the RCA agent reads.

Three scenarios so far:

| Scenario | What happens | Category it feeds |
|---|---|---|
| `healthy` | Runs cleanly, no failure | -- |
| `schema_drift` | Upstream renamed `customer_id` -> `cust_id`; transform crashes with a real `KeyError` | `schema_drift` |
| `data_quality` | 1 of 20 rows' `metadata` JSON is missing the `promo_code` key the enrich stage expects; crashes with a real `KeyError` on that one row | `data_quality` |

## Structure

```
main.py         # entrypoint: parses the scenario arg, sets up logging, orchestrates the run
extract.py      # queries dbo.orders_healthy / orders_drift / orders_dq from SQL Server
validate.py     # generic sanity check only (raises if zero rows extracted) -- no schema-
                #   specific check, so it never leaks the "expected" schema as a hint
transform.py    # computes revenue per customer_id (fails on the drift table)
enrich.py       # data_quality only: reads metadata JSON's promo_code key (fails on the 1
                #   row missing it)
db_config.py    # SQL Server connection string
setup_db.py     # one-time: creates the database + all 3 tables, seeds sample rows
```

## Requirements

- Python 3.11+
- SQL Server reachable at `localhost\JUST_INTO_DS` (edit `db_config.py` if
  yours is named differently) with Windows Integrated auth
- ODBC Driver 17 for SQL Server installed

## Setup

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# one-time: creates the rca_orders_demo database + all 3 tables
python setup_db.py
```

## Run

```powershell
.venv\Scripts\Activate.ps1

python main.py healthy         # succeeds
python main.py schema_drift    # fails with a real KeyError (schema_drift)
python main.py data_quality    # fails with a real KeyError (data_quality)
```

Each run writes its own file to `..\RCA_LOGS\`, named
`sample-pipeline_<timestamp>.log` (microsecond precision, so back-to-back
runs never collide or get merged into one file) -- run any scenario as many
times as you like, nothing gets overwritten.

## Adding a new scenario

Doesn't have to involve the database. The only requirement is a real failure
from real execution. For a DB-backed one:

1. Add a new table to `setup_db.py` (or reuse an existing one) representing
   the condition you want to simulate.
2. Add an entry to `SCENARIO_TABLES` in `extract.py` pointing at it.
3. Wire in a new stage module if the failure needs one (like `enrich.py`
   does for `data_quality`), and call it conditionally in `main.py`'s `run()`.

For something non-DB (a real timeout, a real bad credential, a real resource
limit), just add whatever module produces that failure for real and call it
from `main.py`'s `run()` -- `extract`/`validate`/`transform`/`enrich` aren't
a mandatory shape, just what this pipeline happens to need so far.

The scenario name itself just needs to reach `argparse`'s `choices` in
`main.py`.
