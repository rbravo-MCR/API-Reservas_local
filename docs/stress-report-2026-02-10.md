# Stress Report - 2026-02-10

## Scope

- Tool: Locust (`tests/performance/locust_stressfile.py`)
- Run id: `20260210095735`
- API target: `POST /api/v1/reservations`
- Environment: local (`http://127.0.0.1:8000`)

## Scenarios executed

1. `stress-ramp-500` (500 users, 5 minutes)
2. `stress-spike-500` (500 users, spike, 2 minutes)
3. `stress-recovery-50` (50 users, 2 minutes)
4. `stress-breakpoint-1000` (1000 users, 2 minutes)

## Results

| Scenario | Requests | Failures | Failure rate | p50 | p95 | p99 | Throughput |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| stress-ramp-500 | 8049 | 267 | 3.32% | 14000 ms | 44000 ms | 56000 ms | 24.87 req/s |
| stress-spike-500 | 4913 | 0 | 0.00% | 12000 ms | 16000 ms | 20000 ms | 37.52 req/s |
| stress-recovery-50 | 4288 | 0 | 0.00% | 1300 ms | 2100 ms | 2700 ms | 35.80 req/s |
| stress-breakpoint-1000 | 3783 | 418 | 11.05% | 38000 ms | 48000 ms | 51000 ms | 26.98 req/s |

## Key findings

- Break point appears from `stress-ramp-500` (errors and very high latency tails).
- `stress-breakpoint-1000` confirms instability under extreme concurrency (`11.05%` failures).
- Error signature under failure: HTTP `500` with code `DATABASE_ERROR`.
- Recovery after spike is successful in functional terms: `stress-recovery-50` returned to `0%` failures and lower latency than spike.

## Data integrity validation (run scope)

Source: `artifacts/stress/integrity.md`

- Reservations created in run scope: `20420`
- Outbox rows in run scope: `40840` (expected `2 * reservations`)
- Reservations with outbox count != 2: `0`
- Duplicate reservation codes (global): `0`
- Duplicate reservation codes (run scope): `0`

Conclusion: no data-loss or reservation-code-collision evidence in this stress run scope.

## Recommendations

1. Tune DB pool and timeout settings by environment and re-run stress.
2. Reduce DB round-trips in reservation creation path.
3. Run outbox worker as separate service during production load.
4. Repeat stress in staging with production-like MySQL resources before go-live.

## Artifacts

- `artifacts/stress/summary.md`
- `artifacts/stress/integrity.md`
- `artifacts/stress/stress-ramp-500_stats.csv`
- `artifacts/stress/stress-spike-500_stats.csv`
- `artifacts/stress/stress-recovery-50_stats.csv`
- `artifacts/stress/stress-breakpoint-1000_stats.csv`
