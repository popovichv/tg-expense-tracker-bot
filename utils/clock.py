from datetime import date, datetime

from config import TIMEZONE


def now() -> datetime:
    """The current moment, aware, in the configured timezone."""
    return datetime.now(TIMEZONE)


def today() -> date:
    """The current date where the user is, not where the server runs.

    Everything that needs "today" goes through here, so the bot does not file
    an evening expense under tomorrow when the container clock is UTC.
    """
    return now().date()
