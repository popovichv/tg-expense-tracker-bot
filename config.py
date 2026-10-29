import os
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TG_TOKEN")


def _with_psycopg_driver(url: str) -> str:
    """Point a plain postgres:// URL at the driver SQLAlchemy expects.

    Hosting platforms hand out `postgres://` or `postgresql://`, but SQLAlchemy
    needs the dialect spelled out or it falls back to psycopg2.
    """
    parts = urlsplit(url)
    if parts.scheme in ("postgres", "postgresql"):
        parts = parts._replace(scheme="postgresql+psycopg")
    return urlunsplit(parts)


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Point it at your Postgres database, e.g. "
            "postgresql://user:password@host:5432/dbname"
        )
    return _with_psycopg_driver(url)


DATABASE_URL = get_database_url()
