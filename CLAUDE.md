# Working agreement for Claude sessions in this repo

Read `docs/PLAN.md` first. It holds the architecture, settled decisions and milestones.

## Rules

- **Discuss before changing the plan.** Propose changes to scope, architecture, tools or milestone order
  and wait for agreement. Do not start building a different approach.
- **Learning mode.** For each new layer (first silver table, first dbt model, first test, first effective-date
  join), explain the concept and let Jake write the first piece; review it. After that, template the rest.
- **No coursework framing** anywhere in the repo (course names, problem numbers, assignment wording).
- **Data never enters this repo.** `data/` is gitignored.
- One branch and one pull request per milestone. Keep commits small and descriptive.

## Data

The raw export lives in a private repo. From the repo root:

```bash
git clone https://github.com/JacobWillson13/adventureworks-data.git data
```

This gives `data/raw/*.csv` (72 files, tab-delimited, no header row). Column names and types come from
`config/aw_schema.json`; per-file fixes from `config/ingest_overrides.json`.

## Environment limits

- Cloud sessions cannot reach the Databricks workspace. Write code, tests and bundle config; Jake deploys and
  runs on Databricks and reports results back.
- Local checks available in a session: `python -m pytest -q`, `python scripts/profile_raw.py`,
  `python scripts/bronze_dryrun.py`, `python scripts/silver_dryrun.py` (both need Java 17+ and pyspark).

## Conventions

- Python 3.12+, PySpark 4. Pin `pandas<3` while PySpark is in the environment.
- Unity Catalog: catalog `workspace` (variable `catalog`), schemas `aw_raw`, `aw_bronze`, `aw_silver`, `aw_gold`.
- Table and column names in silver and gold are snake_case.
- Revenue = SubTotal. Analysis window ends 2014-05-31.
- Paste long-running shell commands one at a time (multi-line pastes cancel them on Jake's terminal).
