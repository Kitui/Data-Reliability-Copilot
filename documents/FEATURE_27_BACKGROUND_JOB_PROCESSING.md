# Feature 27 — Background Job Processing

Feature 27 introduces persistent, trackable background audit jobs without changing the deterministic audit engine.

## Delivered

- PostgreSQL/SQLAlchemy-backed job records with workspace scoping.
- Idempotent job creation using workspace and upload checksum.
- Job states: queued, starting, validating, processing, completed, failed and cancelled.
- Local threaded dispatcher for development and single-instance deployments.
- Transport-neutral dispatcher interface retained for Cloud Tasks or Pub/Sub.
- Asynchronous CSV audit endpoint: `POST /audits/upload/async`.
- Job APIs for listing, status, cancellation and retry.
- Frontend upload flow that polls progress and opens the completed audit.
- Worker failure recording and retry support.
- Secure dataset-file integration for queued jobs.
- Migration `0016` for secure upload metadata missing from the supplied baseline.

## API

- `POST /audits/upload/async`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `POST /jobs/{job_id}/cancel`
- `POST /jobs/{job_id}/retry`

## Deployment note

The included dispatcher uses an in-process thread pool and is intended for local development and controlled single-instance deployments. The next production deployment step is to implement the existing `JobDispatcher` interface with Google Cloud Tasks and run handlers in a dedicated Cloud Run worker service.

## Validation

- Dedicated background-job tests passed.
- Storage, dataset, audit workspace, scheduling and quality-rule regression tests passed.
- 34 affected tests passed together.
- The complete suite progressed beyond 79% without a failure before the execution environment timeout.
