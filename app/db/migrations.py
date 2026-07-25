from __future__ import annotations

from alembic import command
from alembic.config import Config

from app.core.config import get_settings


def run_migrations() -> None:
    settings = get_settings()
    config = Config(str(settings.root_dir / "alembic.ini"))
    config.set_main_option("script_location", str(settings.root_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
