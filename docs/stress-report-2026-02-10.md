# Stress Report - 2026-02-10

## Scope

- Tool: Locust (`tests/performance/locust_stressfile.py`)
- API target: `POST /api/v1/reservations`
- Environment: local (`http://127.0.0.1:8000`)
- Baseline run id: `20260210095735`
- Optimized run id: `20260210114648`

## Comparison (before vs after optimization)

| Scenario | Before failures | After failures | Before p95 | After p95 | Before throughput | After throughput |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| stress-ramp-500 | 267 (3.32%) | 38 (0.32%) | 44000 ms | 29000 ms | 24.87 req/s | 36.80 req/s |
| stress-spike-500 | 0 | 0 | 16000 ms | 18000 ms | 37.52 req/s | 39.33 req/s |
| stress-recovery-50 | 0 | 0 | 2100 ms | 1500 ms | 35.80 req/s | 46.75 req/s |
| stress-breakpoint-1000 | 418 (11.05%) | 54 (1.02%) | 48000 ms | 35000 ms | 26.98 req/s | 36.87 req/s |

## Optimized run details

| Scenario | Requests | Failures | Failure rate | p50 | p95 | p99 | Throughput |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| stress-ramp-500 | 12040 | 38 | 0.32% | 9900 ms | 29000 ms | 44000 ms | 36.80 req/s |
| stress-spike-500 | 4992 | 0 | 0.00% | 12000 ms | 18000 ms | 23000 ms | 39.33 req/s |
| stress-recovery-50 | 5650 | 0 | 0.00% | 980 ms | 1500 ms | 2200 ms | 46.75 req/s |
| stress-breakpoint-1000 | 5287 | 54 | 1.02% | 26000 ms | 35000 ms | 42000 ms | 36.87 req/s |

## Integrity validation (optimized run scope)

Source: `artifacts/stress/integrity.md`

- Reservations created in run scope: `28016`
- Outbox rows in run scope: `56032` (expected `2 * reservations`)
- Reservations with outbox count != 2: `0`
- Duplicate reservation codes (global): `0`
- Duplicate reservation codes (run scope): `0`

Conclusion: no data-loss or reservation-code-collision evidence in optimized stress run scope.

## Conclusions

- The optimization round reduced failure rate substantially under stress.
- Break point still starts at high concurrency (`stress-ramp-500`), but with much lower error rate.
- Recovery after spike remains healthy with zero errors and better p95.

## Artifacts

- `artifacts/stress/summary.md`
- `artifacts/stress/integrity.md`
- `artifacts/stress/stress-ramp-500_stats.csv`
- `artifacts/stress/stress-spike-500_stats.csv`
- `artifacts/stress/stress-recovery-50_stats.csv`
- `artifacts/stress/stress-breakpoint-1000_stats.csv`
