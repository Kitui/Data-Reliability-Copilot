from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/restore_postgres.py <backup.dump>")
    backup = Path(sys.argv[1]).resolve()
    if not backup.exists():
        raise SystemExit(f"Backup not found: {backup}")
    database_url = os.environ.get("DRC_DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        raise SystemExit("DRC_DATABASE_URL must point to PostgreSQL.")
    parsed = urlparse(database_url.replace("postgresql+psycopg", "postgresql"))
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password
    command = [
        "pg_restore",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "--host",
        parsed.hostname or "localhost",
        "--port",
        str(parsed.port or 5432),
        "--username",
        parsed.username or "postgres",
        "--dbname",
        parsed.path.lstrip("/"),
        str(backup),
    ]
    subprocess.run(command, check=True, env=env)


if __name__ == "__main__":
    main()
