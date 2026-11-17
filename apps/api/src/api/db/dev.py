"""Tools that only run against a development database.

They refuse to run unless APP_ENV=development is set, in the environment or in
the repo root .env file.

    uv run python -m api.db.dev drop-schema    # make db-fresh runs this
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.orm import Session

REPO_ROOT_ENV = Path(__file__).resolve().parents[5] / ".env"
DEV_ENV = "development"


class NotDevelopment(Exception):
    """APP_ENV is not "development", so we must not touch the database."""


def require_development() -> None:
    """Raise NotDevelopment unless APP_ENV is "development".

    A missing APP_ENV counts as not development, so a server without the
    setting can never be wiped or seeded by accident.
    """
    load_dotenv(REPO_ROOT_ENV)
    app_env = os.environ.get("APP_ENV")
    if app_env != DEV_ENV:
        raise NotDevelopment(
            f'APP_ENV is {app_env!r}, not "{DEV_ENV}". '
            f"Add APP_ENV={DEV_ENV} to the repo root .env file on a dev machine."
        )


def drop_schema(db: Session) -> None:
    """Delete every table, type and the alembic version, so all migrations run again.

    This also works when the migrations are broken, unlike `alembic downgrade base`.
    """
    require_development()
    db.execute(text("DROP SCHEMA public CASCADE"))
    db.execute(text("CREATE SCHEMA public"))
    db.commit()


def main(argv: list[str]) -> int:
    if argv != ["drop-schema"]:
        print("usage: python -m api.db.dev drop-schema", file=sys.stderr)
        return 2
    try:
        require_development()
    except NotDevelopment as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    from api.db.session import session_local

    with session_local() as db:
        drop_schema(db)
    print("Dropped and recreated the public schema.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
