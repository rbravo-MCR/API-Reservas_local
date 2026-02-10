# Performance Report - 2026-02-10

## Scope

- Tool: Locust (headless)
- API under test: `POST /api/v1/reservations` and `GET /api/v1/health`
- Environment: local (`http://127.0.0.1:8000`)
- Threshold objective: p95 < 500 ms

## Executed scenarios

1. `load-50-users` (50 users, 3 minutes)
2. `load-100-users` (100 users, 3 minutes)
3. `sustained-10m` (100 users, 10 minutes)

## Results (POST /api/v1/reservations)

| Scenario | Requests | Failures | Failure rate | p50 | p95 | p99 | Throughput |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| load-50-users | 6303 | 0 | 0.00% | 1100 ms | 2300 ms | 3700 ms | 35.12 req/s |
| load-100-users | 3138 | 53 | 1.69% | 2800 ms | 20000 ms | 38000 ms | 16.32 req/s |
| sustained-10m | 16113 | 32 | 0.20% | 2700 ms | 7400 ms | 30000 ms | 26.81 req/s |

Error observed in failures:

- `500 DATABASE_ERROR` on `POST /api/v1/reservations` (53 occurrences in `load-100-users`, 32 in `sustained-10m`)

## Bottlenecks identified

1. Database connection contention/saturation.
- Evidence: failures are only `DATABASE_ERROR` under higher concurrency, with long tails up to ~55-60 seconds.
- The session factory uses `pool_size=10` and `max_overflow=20` (max 30 connections): `src/reservas_api/infrastructure/db/session.py:31`, `src/reservas_api/infrastructure/db/session.py:32`.
- At 100 users, this is likely insufficient for the request pattern.

2. Too many DB round-trips per reservation creation.
- Code generation performs a DB read (`exists_code`) before persisting: `src/reservas_api/application/use_cases/generate_reservation_code_use_case.py:48`, `src/reservas_api/infrastructure/repositories/mysql_reservation_repository.py:45`.
- Save flow does pre-select + flush + refresh: `src/reservas_api/infrastructure/repositories/mysql_reservation_repository.py:69`, `src/reservas_api/infrastructure/repositories/mysql_reservation_repository.py:81`, `src/reservas_api/infrastructure/repositories/mysql_reservation_repository.py:82`.
- Outbox persists two events per request: `src/reservas_api/infrastructure/outbox/outbox_event_publisher.py:57`, `src/reservas_api/infrastructure/outbox/outbox_event_publisher.py:63`.

3. Debug SQL logging in local profile adds overhead during load.
- Engine uses `echo=app_settings.app_debug`: `src/reservas_api/infrastructure/db/session.py:29`.
- In local env, `APP_DEBUG` is commonly true, producing high I/O overhead when load testing.

4. Global in-memory rate limiter lock introduces serialized section.
- All requests pass through one `asyncio.Lock` for rate bookkeeping: `src/reservas_api/api/middleware/rate_limiter.py:31`, `src/reservas_api/api/middleware/rate_limiter.py:44`.
- This is not the main bottleneck but adds contention under concurrency.

## Conclusion

- The current implementation does not meet the p95 objective (<500 ms) in any scenario.
- Primary bottleneck is DB path pressure (connection pool + query/write count per request), with secondary overhead from debug logging.

## Recommended actions (priority order)

1. Externalize and tune DB pool settings (`pool_size`, `max_overflow`, `pool_timeout`) per environment.
2. Eliminate `exists_code` pre-check and rely on unique index + retry on `IntegrityError`.
3. Remove redundant pre-select/refresh in create path and use insert-first flow.
4. Keep `APP_DEBUG=false` for load/stress runs.
5. Replace global lock strategy in rate limiter for load-test profile or skip middleware during benchmarks.
6. Re-run scenarios after changes and compare p95/p99, failure rate and throughput.

## Artifacts

- `artifacts/performance/summary.md`
- `artifacts/performance/load-50-users_stats.csv`
- `artifacts/performance/load-100-users_stats.csv`
- `artifacts/performance/sustained-10m_stats.csv`
- `artifacts/performance/load-100-users_failures.csv`
- `artifacts/performance/sustained-10m_failures.csv`
