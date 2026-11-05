import calendar
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


def month_start(value: date) -> date:
    """The first day of the month a date falls in.

    A month is identified by this date throughout, so a report and the buttons
    that move between months agree on what "November" is without passing a
    year and a month number around separately.
    """
    return value.replace(day=1)


def month_end(value: date) -> date:
    """The last day of the month a date falls in."""
    return value.replace(day=calendar.monthrange(value.year, value.month)[1])


def shift_month(month: date, offset: int) -> date:
    """The first day of the month `offset` months away from this one.

    Counted in months rather than days, so stepping back from the 31st cannot
    land in the wrong month, and crossing a year boundary needs no special
    case.
    """
    index = month.year * 12 + month.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)
