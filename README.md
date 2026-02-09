# Reservas API

API backend para creación y gestión de reservas con FastAPI, MySQL y arquitectura hexagonal.

## Stack

- Python 3.14+
- FastAPI + Pydantic v2
- SQLModel + MySQL (`aiomysql`)
- UV para entorno/dependencias
- Alembic para migraciones
- Pytest + Hypothesis + Ruff

## Instalación

```bash
uv sync --group dev
```

## Configuración

1. Crear `.env` desde `.env.example`.
2. Ajustar conexión MySQL y credenciales externas.

Variables clave:

- `DATABASE_URL` o (`MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`)
- `STRIPE_API_BASE_URL`, `STRIPE_API_KEY`
- `PROVIDER_API_BASE_URL`, `PROVIDER_API_KEY`
- `EXTERNAL_API_TIMEOUT_SECONDS`
- `FORCE_HTTPS`, `TLS_CERT_FILE`, `TLS_KEY_FILE`
- `RATE_LIMIT_REQUESTS_PER_MINUTE`, `RATE_LIMIT_RESERVATIONS_PER_MINUTE`

## Ejecución local

```bash
uv run uvicorn reservas_api.main:app --reload --app-dir src
```

## Migraciones (Alembic)

```bash
# aplicar migraciones
uv run alembic upgrade head

# crear nueva revisión
uv run alembic revision --autogenerate -m "describe change"
```

## Seed de desarrollo

```bash
uv run python scripts/seed_dev_data.py
```

Esto carga proveedores y oficinas base en `suppliers` y `offices`.

## OpenAPI/Swagger

FastAPI expone documentación interactiva en:

- `GET /docs`
- `GET /redoc`

Exportar especificación OpenAPI:

```bash
uv run python scripts/export_openapi.py
```

Salida: `docs/openapi.json`.

## Ejemplos de API

Crear reserva:

```bash
curl -X POST "http://localhost:8000/api/v1/reservations" \
  -H "Content-Type: application/json" \
  -d '{
    "supplier_code": "SUP01",
    "pickup_office_code": "MAD01",
    "dropoff_office_code": "MAD02",
    "pickup_datetime": "2026-12-01T10:00:00Z",
    "dropoff_datetime": "2026-12-03T10:00:00Z",
    "total_amount": "180.50",
    "customer": {
      "first_name": "Ana",
      "last_name": "Perez",
      "email": "ana@example.com",
      "phone": "+34123456789"
    },
    "vehicle": {
      "vehicle_code": "VH001",
      "model": "Corolla",
      "category": "Economy"
    }
  }'
```

Health check:

```bash
curl "http://localhost:8000/api/v1/health"
```

## Códigos de error

- `400`: regla de negocio inválida
- `422`: validación de payload
- `429`: límite de tasa excedido
- `500`: error interno/bd

Detalle extendido en `docs/api-errors.md`.

## Documentación adicional

- Arquitectura: `docs/architecture.md`
- Despliegue: `docs/deployment-guide.md`
- OpenAPI exportado: `docs/openapi.json`

## Pruebas y calidad

```bash
uv run ruff check src tests scripts alembic
uv run pytest -q
```

## Estructura

```text
src/reservas_api/
  api/
  application/
  domain/
  infrastructure/
  shared/
alembic/
scripts/
tests/
docs/
```
