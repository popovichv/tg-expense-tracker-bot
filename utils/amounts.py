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


def split_amount(text: str) -> tuple[Decimal, str | None] | None:
    """Read a line like "12.50 coffee" as an amount and what it was spent on.

    The amount is as much of the start of the line as still reads as one, so a
    sum written with `+` is kept whole and only what follows it becomes the
    description -- "10 + 5 coffee" is 15 spent on coffee, not 10 spent on
    "+ 5 coffee". Taking the longest match rather than the first is what makes
    that work, since "10" parses on its own too.

    None means the line does not begin with a usable amount at all, which is
    the caller's cue to say so rather than to log anything.
    """
    tokens = text.split()
    amount = None
    taken = 0

    for count in range(1, len(tokens) + 1):
        candidate = parse_amount(" ".join(tokens[:count]))

        if candidate is not None:
            amount, taken = candidate, count

    if amount is None:
        return None

    return amount, " ".join(tokens[taken:]) or None
