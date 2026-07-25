# Feature 28 Installation

1. Preserve your `.env` and credentials.
2. Replace the project with this package.
3. Set `DRC_ENABLE_INTERNAL_SCHEDULER=false`.
4. Add a random `DRC_SCHEDULER_TOKEN` of at least 24 characters.
5. Run `alembic upgrade head`.
6. Start FastAPI normally.
7. Trigger due schedules with either:
   - `python -m app.scheduling.dispatch_due`, or
   - `POST /schedules/dispatch` with `X-DRC-Scheduler-Token`.
