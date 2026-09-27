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

Six scenarios so far:

| Scenario | What happens | Category it feeds |
|---|---|---|
| `healthy` | Runs cleanly, no failure | -- |
| `schema_drift` | Upstream renamed `customer_id` -> `cust_id`; transform crashes with a real `KeyError` | `schema_drift` |
| `data_quality` | 1 of 20 rows' `metadata` JSON is missing the `promo_code` key the enrich stage expects; crashes with a real `KeyError` on that one row | `data_quality` |
| `data_quality_malformed` | Same category, a different defect: 1 of 20 rows' `metadata` isn't valid JSON at all; crashes with a real `JSONDecodeError` | `data_quality` |
| `timeout` | Join to `customer_region_history` omits its effective-date predicate, so every order fans out against every history row for its customer; a real, oversized result set blows past the query timeout with a real pyodbc error | `infra_timeout` |
| `code_bug` | Reads the same data as `healthy` (schema and data are both fine) -- `compute_top_customer_share` wrongly assumes more than 5 customers exist, so excluding the top 5 (out of exactly 5) leaves nothing to average; crashes with a real `ZeroDivisionError` | `code_bug` |

## Structure

```
main.py                    # entrypoint: parses the scenario arg, sets up logging, dispatches
                            #   to exactly one scenario's run()
setup_db.py                # one-time: creates the database + all 3 tables, seeds sample rows

config/
  db_config.py              # SQL Server connection string

src/
  pipeline/
    extract.py              # extract(): queries orders_healthy / orders_drift / orders_dq / etc
                             #   extract_slow_join(): the missing-predicate join for `timeout`
    validate.py              # generic sanity check only (raises if zero rows extracted) -- no
                              #   schema-specific check, so it never leaks the "expected" schema
    transform.py              # computes revenue per customer_id (fails on the drift table)
    enrich.py                 # reads metadata JSON's promo_code key (fails on missing/bad JSON)
    report.py                  # compute_top_customer_share(): the code_bug's off-by-one
  scenarios/
    healthy.py                 # wires extract -> validate -> transform; no failure
    schema_drift.py             # same wiring against the drifted table; real KeyError
    data_quality.py              # same wiring plus enrich; real KeyError on the 1 gapped row
    data_quality_malformed.py     # same wiring, different table; real JSONDecodeError
    timeout.py                    # calls extract_slow_join(); real pyodbc query-timeout error
    code_bug.py                    # reads healthy data; real ZeroDivisionError in report.py
```

Each scenario module exposes a single `run()` function and calls only the
pipeline stages it needs -- no shared branching logic. `main.py` just looks up
the requested scenario in a `{name: run}` registry and calls that one
function.

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

python main.py healthy                   # succeeds
python main.py schema_drift              # fails with a real KeyError (schema_drift)
python main.py data_quality              # fails with a real KeyError (data_quality)
python main.py data_quality_malformed    # fails with a real JSONDecodeError (data_quality)
python main.py timeout                   # fails with a real pyodbc query-timeout error
python main.py code_bug                  # fails with a real ZeroDivisionError (code_bug)

python main.py                 # no arg: runs every scenario one by one, each
                                #   getting its own log file; one scenario's
                                #   failure doesn't stop the rest from running
```

Each run writes its own file to `..\RCA_LOGS\`, named
`sample-pipeline_<timestamp>.log` (microsecond precision, so back-to-back
runs never collide or get merged into one file) -- run any scenario as many
times as you like, nothing gets overwritten.

`timeout`'s row counts (`setup_db.py`'s `TIMEOUT_*` constants) and query
timeout (`extract.py`'s `TIMEOUT_QUERY_SECONDS`) don't reliably produce a
clean, fast timeout in practice -- the one real run so far took ~84 seconds
(not the configured 3s) and raised a generic `pyodbc.Error: ('HY000', 'The
driver did not supply an error!')` rather than a clean "query timeout
expired." That's because `SQL_ATTR_QUERY_TIMEOUT` mostly governs the
`execute()` call, not the `fetchall()` phase where most of this scenario's
actual time goes (transferring a ~16M-row result set). It's still a genuine
failure from genuine execution, just not the fast, clean one originally
designed. If you need it faster/cleaner, lower the row counts and/or add an
explicit `WAITFOR DELAY` floor to the query instead of relying solely on the
client-side timeout.

## Adding a new scenario

Doesn't have to involve the database. The only requirement is a real failure
from real execution, and each scenario gets its own `run()` function -- never
branching logic bolted onto an existing one. For a DB-backed one:

1. Add a new table to `setup_db.py` (or reuse an existing one) representing
   the condition you want to simulate.
2. Add an entry to `SCENARIO_TABLES` in `src/pipeline/extract.py` pointing at it.
3. Add `src/scenarios/<name>.py` with a single `run()` function that wires
   together whatever pipeline stages it needs (reuse `src/pipeline/*` stages;
   add a new stage module there first if the failure needs one, like
   `enrich.py` does for `data_quality`).
4. Register `"<name>": <name>.run` in the `SCENARIOS` dict in `main.py`.

For something non-DB (a real timeout, a real bad credential, a real resource
limit), the shape is the same: `src/scenarios/<name>.py` with a `run()` that
produces that failure for real, registered in `main.py`.
`extract`/`validate`/`transform`/`enrich` aren't a mandatory shape for every
scenario -- just what this pipeline happens to need so far.

The scenario name itself just needs to be a key in `SCENARIOS` in `main.py`
(that's also what feeds `argparse`'s `choices`).
