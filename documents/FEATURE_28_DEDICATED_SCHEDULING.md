# Feature 28 — Dedicated Scheduling and Job Dispatch

## Overview

Scheduled audits no longer execute inside the FastAPI web process. A dedicated dispatcher claims due schedules, advances their next occurrence transactionally, creates queued run records, and sends persistent background jobs to the Feature 27 worker.

## Components

- `app/scheduling/service.py` — atomic due-schedule claiming and job creation
- `app/scheduling/dispatch_due.py` — command-line dispatcher for cron or Cloud Run Jobs
- `POST /schedules/dispatch` — token-protected Cloud Scheduler endpoint
- `scheduled_audit` background-job handler
- queued manual **Run now** workflow with frontend progress polling
- migration `0017_dedicated_scheduling`

## Required configuration

```env
DRC_ENABLE_INTERNAL_SCHEDULER=false
DRC_SCHEDULER_TOKEN=<at-least-24-random-characters>
```

Cloud Scheduler should call `POST /schedules/dispatch` with the header:

```text
X-DRC-Scheduler-Token: <DRC_SCHEDULER_TOKEN>
```

For a dedicated process or local cron, run:

```powershell
python -m app.scheduling.dispatch_due
```

## Reliability controls

- PostgreSQL row locking with `SKIP LOCKED`
- next-run advancement before claim release
- occurrence-based idempotency keys
- persistent queued, in-progress, completed, and failed run records
- background-job linkage for traceability
- manual runs do not alter the normal recurring next-run time
