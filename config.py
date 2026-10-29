import os
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TG_TOKEN")


def get_timezone() -> ZoneInfo:
    """The timezone every date in the bot is interpreted in.

    Telegram does not report a user's timezone, so dates come from this
    setting rather than from the server clock, which in a container is UTC.
    """
    name = os.getenv("TIMEZONE", "UTC")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise RuntimeError(
            f"TIMEZONE is not a usable IANA timezone: {name!r}. Use a name like "
            "America/Toronto, and make sure the tzdata package is installed."
        ) from exc


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
TIMEZONE = get_timezone()
