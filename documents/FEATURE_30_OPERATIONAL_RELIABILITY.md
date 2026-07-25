q# Feature 30 — Operational Reliability

Feature 30 adds production observability and recovery foundations without changing data-quality behaviour.

## Delivered

- JSON structured request logging with request IDs, routes, response status and duration.
- Separate `/health/live` and `/health/ready` endpoints.
- Readiness checks for PostgreSQL and configured object storage.
- Prometheus-compatible `/metrics` endpoint with optional token protection.
- Admin operations summary for HTTP and background-job health.
- Threshold-driven persistent operational alerts with cooldown deduplication.
- PostgreSQL backup and restore scripts based on `pg_dump` and `pg_restore`.
- Migration `0019_operational_reliability`.

## Endpoints

- `GET /health/live`
- `GET /health/ready`
- `GET /metrics`
- `GET /operations/summary`
- `POST /operations/alerts/evaluate`
- `GET /operations/alerts`

## Backup

```powershell
python scripts/backup_postgres.py
```

Restore into a controlled empty or disposable environment first:

```powershell
python scripts/restore_postgres.py backups/drc-postgres-YYYYMMDDTHHMMSSZ.dump
```

Production backups should be scheduled outside the web process and copied to a separately protected bucket with retention and object versioning.
