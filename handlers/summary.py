"""The block of detail an expense is shown as, wherever it is shown.

One layout in one place, so the confirmation an expense is added with and the
card it is edited on cannot drift apart.

A rich message table, which means the escaping this module used to do is gone
rather than merely tidied away: cell text travels as data, so a category or a
description containing `<` arrives as itself instead of making Telegram
reject the whole message as malformed HTML. The dashed divider went with it,
the table drawing its own rules.
"""

from datetime import date
from decimal import Decimal

from utils.money import format_amount

MISSING_DESCRIPTION = "N/A"


def long_date(value: date) -> str:
    """A date as it is written out, rather than as it is stored.

    Assembled from the parts rather than with a format directive, because the
    one that drops the padding zero from the day is `%-d` on Linux and `%#d`
    on Windows, and this bot is developed on one and deployed to the other.
    """
    return f"{value:%B} {value.day}, {value.year}"


def expense_fields(
    category: str,
    description: str | None,
    amount: Decimal,
    spent_at: date,
) -> list[tuple[str, str]]:
    """One expense as label and value, in the order it is always shown in."""
    return [
        ("Category", category),
        ("Description", description or MISSING_DESCRIPTION),
        ("Amount", format_amount(amount)),
        ("Date", long_date(spent_at)),
    ]


def expense_blocks(
    title: str,
    category: str,
    description: str | None,
    amount: Decimal,
    spent_at: date,
) -> list[dict]:
    """One expense in full, captioned with what is being shown and why.

    The labels carry their own bold rather than being header cells. A header
    cell takes a shade of its own, which left the stripe covering only the
    half of each row that was not a label; as ordinary cells, every row is
    striped across its whole width.

    This table has no header row for the same reason /spending and
    /list_categories do: there is nothing to label, the fields being their own
    labels down the side.

    The title says what just happened -- the expense was recorded, or its
    amount was changed -- so a result needs no line of its own above the
    detail it is a result about.
    """
    cells = [
        [{"text": {"type": "bold", "text": label}}, {"text": value}]
        for label, value in expense_fields(category, description, amount, spent_at)
    ]

    return [
        {
            "type": "table",
            "cells": cells,
            "caption": {"type": "bold", "text": title},
            "is_bordered": True,
            "is_striped": True,
        }
    ]
