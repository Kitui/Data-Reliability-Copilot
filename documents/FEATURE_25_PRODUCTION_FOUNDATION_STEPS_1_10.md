# Feature 25 — Production Foundation: Steps 1–10

## Completed

1. Created a clean source baseline from the supplied archive.
2. Removed `.venv`, caches, runtime databases, uploaded files, generated data, and E2E backups.
3. Strengthened `.gitignore` and retained empty runtime directories with `.gitkeep`.
4. Replaced unsafe example administrator credentials with explicit placeholders.
5. Added production configuration validation and environment controls.
6. Generalised brittle frontend asset-version tests.
7. Added PostgreSQL dependencies and a local PostgreSQL 16 `docker-compose.yml` definition.
8. Added Alembic revision `0015` and verified the full migration chain on a clean database.
9. Added a transport-neutral object-storage abstraction with local and Google Cloud Storage implementations.
10. Added a background-job model, statuses, job types, idempotency constraint, worker interface, and dispatcher interface.

## Runtime controls

- `DRC_RUN_MIGRATIONS`: controls startup migrations.
- `DRC_ENABLE_INTERNAL_SCHEDULER`: permits the legacy scheduler locally but must be disabled in production.
- `DRC_STORAGE_BACKEND`: `local` or `gcs`.
- `DRC_STORAGE_ROOT`: local storage root.
- `DRC_GCS_BUCKET`: required for GCS.
- `DRC_MAX_UPLOAD_BYTES`: upload-size foundation setting.

## PostgreSQL development command

```bash
docker compose up -d postgres
```

Then configure:

```env
DRC_DATABASE_URL=postgresql+psycopg://drc:drc-local-only@localhost:5432/drc
```

Run migrations:

```bash
alembic upgrade head
```

## Validation performed

- Python application compilation passed.
- Alembic revisions `0001` through `0015` passed on a clean database.
- The `background_jobs` table was verified after migration.
- Copilot test module: 10 passed.
- Remaining late-suite test group: 28 passed.
- Earlier suite execution reached 75% with no failures after corrections.
- Individual test modules executed during isolation passed.

## Limitation

A live PostgreSQL container could not be started in the execution environment because Docker is not installed. The Compose definition, PostgreSQL driver, SQLAlchemy configuration, and migration path are included for local validation.

## Next implementation boundary

The storage abstraction and job interfaces are foundations. Existing upload and audit routes still use the current synchronous local-file flow to preserve behaviour. The next phase should migrate those routes incrementally to object storage and queued job execution.
