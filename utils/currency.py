"""Currency codes, their symbols, and where the symbol sits.

Placement is a convention of the place the currency is used rather than
something derivable from the code, so it is recorded per currency here.
Anything not listed falls back to showing the code after the amount, which
reads correctly for any currency even when its symbol is unknown.
"""

from decimal import Decimal

DEFAULT_CURRENCY = "USD"

BEFORE = True
AFTER = False

CURRENCIES = {
    "USD": ("$", BEFORE),
    "CAD": ("$", BEFORE),
    "AUD": ("$", BEFORE),
    "NZD": ("$", BEFORE),
    "SGD": ("$", BEFORE),
    "HKD": ("$", BEFORE),
    "MXN": ("$", BEFORE),
    "ARS": ("$", BEFORE),
    "CLP": ("$", BEFORE),
    "COP": ("$", BEFORE),
    "GBP": ("£", BEFORE),
    "JPY": ("¥", BEFORE),
    "CNY": ("¥", BEFORE),
    "INR": ("₹", BEFORE),
    "KRW": ("₩", BEFORE),
    "ILS": ("₪", BEFORE),
    "PHP": ("₱", BEFORE),
    "THB": ("฿", BEFORE),
    "TRY": ("₺", BEFORE),
    "ZAR": ("R", BEFORE),
    "BRL": ("R$", BEFORE),
    "CHF": ("CHF", BEFORE),
    "EUR": ("€", AFTER),
    "PLN": ("zł", AFTER),
    "UAH": ("₴", AFTER),
    "CZK": ("Kč", AFTER),
    "SEK": ("kr", AFTER),
    "NOK": ("kr", AFTER),
    "DKK": ("kr", AFTER),
    "ISK": ("kr", AFTER),
    "HUF": ("Ft", AFTER),
    "RON": ("lei", AFTER),
    "RUB": ("₽", AFTER),
    "KZT": ("₸", AFTER),
    "BGN": ("лв", AFTER),
    "VND": ("₫", AFTER),
}


def normalize(code: str) -> str | None:
    """Return the canonical form of a currency code, or None if it isn't one.

    Any three-letter code is accepted rather than only the ones listed above,
    so nobody is locked out of their own currency; an unlisted one simply
    displays as the code.
    """
    code = code.strip().upper()
    if len(code) == 3 and code.isascii() and code.isalpha():
        return code
    return None


def symbol_for(code: str) -> str:
    symbol, _ = CURRENCIES.get(code, (code, AFTER))
    return symbol


def format_amount(amount: Decimal, code: str) -> str:
    """Render an amount the way the currency is usually written."""
    symbol, before = CURRENCIES.get(code, (code, AFTER))
    figure = f"{amount:.2f}"

    if before:
        separator = "" if len(symbol) == 1 else " "
        return f"{symbol}{separator}{figure}"

    return f"{figure} {symbol}"
