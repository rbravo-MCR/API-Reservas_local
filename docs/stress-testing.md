# Stress Testing

This project includes a dedicated stress test workflow with Locust.

## Scenarios

1. `stress-ramp-500`: gradual ramp to 500 users.
2. `stress-spike-500`: spike load with abrupt user ramp.
3. `stress-recovery-50`: post-spike recovery validation.
4. `stress-breakpoint-1000`: high-concurrency pressure to detect break point.

## How to run

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_stress_tests.ps1 -StartLocalApi
```

Optional arguments:

- `-ApiHost` to target another environment.
- `-StressRunId` to force a custom run id.
- `-StrictSummary` to fail command when summary checks fail.
- `-AppendResults` to keep previous stress artifacts.

When `-StartLocalApi` is enabled, the runner sets:

- `APP_DEBUG=false`
- High rate-limit values for benchmark traffic

## Output

All artifacts are generated under `artifacts/stress/`:

- `stress-*_stats.csv`
- `stress-*_failures.csv`
- `stress-*.html`
- `integrity.md`
- `summary.md`

## Integrity checks

`scripts/validate_stress_integrity.py` validates:

- no duplicate reservation codes,
- outbox consistency (2 events per created reservation),
- run-scope integrity using stress-run email marker.
