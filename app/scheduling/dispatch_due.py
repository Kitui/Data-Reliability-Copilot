from __future__ import annotations

from app.db.migrations import run_migrations
from app.scheduling.service import dispatch_due_schedules


def main() -> None:
    run_migrations()
    jobs = dispatch_due_schedules()
    print(f"Dispatched {len(jobs)} scheduled audit job(s).")


if __name__ == "__main__":
    main()
