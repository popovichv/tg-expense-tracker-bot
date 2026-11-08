"""How an amount is written, wherever one is shown.

One currency throughout, so an amount is a figure and a symbol and nothing
has to be carried alongside it. What this replaced was a table of codes and
symbol placements, needed back when each expense remembered the currency it
was recorded in.
"""

from decimal import Decimal


def format_amount(amount: Decimal) -> str:
    """An amount as money, always to two places."""
    return f"${amount:.2f}"
