# Performance Testing

This project uses Locust for load and sustained performance testing of the API.

## Scope

- Endpoint under load: `POST /api/v1/reservations`
- Health baseline: `GET /api/v1/health`
- Metrics collected: p50, p95, p99, throughput (req/s), error count
- Target threshold: p95 < 500 ms

## Implemented Scenarios

1. `load-50-users`: 50 concurrent users for 3 minutes
2. `load-100-users`: 100 concurrent users for 3 minutes
3. `sustained-10m`: 100 concurrent users for 10 minutes

## Files

- Locust script: `tests/performance/locustfile.py`
- Scenario runner: `scripts/run_performance_tests.ps1`
- CSV summary generator: `scripts/summarize_performance_results.py`

## How To Run

1. Start the API (or let the runner start it).
2. Execute:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_performance_tests.ps1 -StartLocalApi
```

Quick smoke validation (30 seconds):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_performance_tests.ps1 -StartLocalApi -ScenarioProfile smoke
```

If the API is already running, omit `-StartLocalApi` and optionally pass another host:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_performance_tests.ps1 -ApiHost http://127.0.0.1:8000
```

## Output

Generated under `artifacts/performance/`:

- `<scenario>_stats.csv`
- `<scenario>_failures.csv`
- `<scenario>.html`
- `summary.md`

`summary.md` includes per-scenario p50/p95/p99, throughput and a pass/fail check against p95 threshold.
Use `-StrictSummary` if you want non-zero exit code when thresholds are not met.
Use `-AppendResults` if you want to keep previous CSV/HTML files in the same output directory.

## Notes

- Default API rate limits are too low for load testing; the runner raises them automatically when `-StartLocalApi` is used.
- DB pool tuning can be configured via env (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_SECONDS`, `DB_POOL_RECYCLE_SECONDS`) when needed.
- For representative numbers, run against an environment with MySQL and realistic data volume.
