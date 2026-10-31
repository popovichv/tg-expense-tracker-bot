"""The block of detail an expense is shown as, wherever it is shown.

One layout in one place, so the confirmation an expense is added with and the
card it is edited on cannot drift apart.
"""

import html
from datetime import date
from decimal import Decimal

from utils import currency

MISSING_DESCRIPTION = "N/A"

DIVIDER = "----------------------------"


def expense_summary(
    title: str,
    category: str,
    description: str | None,
    amount: Decimal,
    code: str,
    spent_at: date,
) -> str:
    """One expense in full, under a heading that says why it is being shown.

    Everything the user supplied is escaped: a category or description
    containing `<` would otherwise make Telegram reject the whole message as
    malformed HTML, and the message would simply never arrive.

    The title carries what just happened -- the expense was recorded, or its
    amount was changed -- so a result needs no line of its own above the
    detail it is a result about.
    """
    return (
        f"<b>{html.escape(title)}</b>\n"
        f"{DIVIDER}\n"
        f"<b>Category:</b> {html.escape(category)}\n"
        f"<b>Description:</b> {html.escape(description or MISSING_DESCRIPTION)}\n"
        f"<b>Amount:</b> {html.escape(currency.format_amount(amount, code))}\n"
        f"<b>Date:</b> {spent_at}"
    )
