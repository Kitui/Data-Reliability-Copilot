from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def main() -> None:
    database_url = os.environ.get("DRC_DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        raise SystemExit("DRC_DATABASE_URL must point to PostgreSQL.")
    target_dir = Path(os.environ.get("DRC_BACKUP_DIR", "backups")).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = target_dir / f"drc-postgres-{timestamp}.dump"
    parsed = urlparse(database_url.replace("postgresql+psycopg", "postgresql"))
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password
    command = [
        "pg_dump", "--format=custom", "--no-owner", "--no-privileges",
        "--host", parsed.hostname or "localhost", "--port", str(parsed.port or 5432),
        "--username", parsed.username or "postgres", "--file", str(output),
        parsed.path.lstrip("/"),
    ]
    subprocess.run(command, check=True, env=env)
    print(output)


if __name__ == "__main__":
    main()
