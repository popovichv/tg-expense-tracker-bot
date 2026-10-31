"""Parsing for amounts as people type them into a chat."""

from decimal import Decimal, InvalidOperation

# What the amount column holds: Numeric(12, 2), so ten digits before the
# point. Rejected here rather than passed on, so an impossible figure is a
# re-prompt and not a database error the user sees as "something went wrong".
MAX_AMOUNT = Decimal("9999999999.99")


def parse_amount(text: str) -> Decimal | None:
    """Read a typed amount, or return None if it is not a usable one.

    Accepts a sum written with `+`, so a receipt can be entered as the
    figures on it rather than added up by hand first, and a comma as the
    decimal separator, which is what most of the world's keyboards offer.
    """
    parts = [part.strip() for part in text.strip().replace(",", ".").split("+")]

    try:
        amount = sum(Decimal(part) for part in parts)
    except (InvalidOperation, ValueError):
        return None

    if not amount.is_finite() or amount <= 0 or amount > MAX_AMOUNT:
        return None

    return amount
