# Performance Report - 2026-02-10

## Scope

- Tool: Locust (headless)
- API under test: `POST /api/v1/reservations` and `GET /api/v1/health`
- Environment: local (`http://127.0.0.1:8000`)
- Threshold objective: p95 < 500 ms

## Optimization round applied

1. Insert-first persistence path in repository (removed pre-select and refresh in create path).
2. Removed global async lock in in-memory rate limiter.
3. DB pool settings externalized by env with safe defaults.
4. Benchmark runner forces `APP_DEBUG=false` for load runs.

## Results comparison (POST /api/v1/reservations)

| Scenario | Before failures | After failures | Before p95 | After p95 | Before throughput | After throughput |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| load-50-users | 0 | 0 | 2300 ms | 1600 ms | 35.12 req/s | 46.11 req/s |
| load-100-users | 53 | 0 | 20000 ms | 4700 ms | 16.32 req/s | 44.53 req/s |
| sustained-10m | 32 | 0 | 7400 ms | 3800 ms | 26.81 req/s | 47.92 req/s |

## Optimized run details

Run generated at: `2026-02-10T17:46:21Z`

| Scenario | Requests | Failures | p50 | p95 | p99 | Throughput |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| load-50-users | 8283 | 0 | 920 ms | 1600 ms | 2200 ms | 46.11 req/s |
| load-100-users | 8028 | 0 | 1900 ms | 4700 ms | 6800 ms | 44.53 req/s |
| sustained-10m | 28766 | 0 | 1800 ms | 3800 ms | 6800 ms | 47.92 req/s |

## Conclusion

- The optimization round removed `DATABASE_ERROR` in the executed performance scenarios.
- Throughput improved significantly in all scenarios.
- p95 is still above the target (<500 ms), so further optimization is still required for SLA compliance.

## Artifacts

- `artifacts/performance/summary.md`
- `artifacts/performance/load-50-users_stats.csv`
- `artifacts/performance/load-100-users_stats.csv`
- `artifacts/performance/sustained-10m_stats.csv`
