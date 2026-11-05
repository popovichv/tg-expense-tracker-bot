"""One month's spending, grouped by category, as a rich message table.

A parent category's figure is its whole branch: what was logged directly
against it plus everything in its subcategories, since that is what a category
total means to the person reading it. Where a parent holds both, the direct
part gets a row of its own, so the subcategory rows and the parent figure
visibly add up instead of leaving a gap the reader has to account for.

Nothing is ever added across currencies, because an expense keeps the one it
was recorded in and /set_currency changes only what is logged afterwards. A
month holding more than one currency gets a table each, and the caption names
the code so the two cannot be mistaken for one another.

Rows run biggest first rather than alphabetically, which is the one place this
bot departs from the ordering its pickers use: a report is read to find where
the money went, and that answer should be at the top.

The month on display rides in the callback data of the buttons that move
between months, so the report keeps no conversation state and its buttons
still work after a restart.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from handlers.rich import edit_rich, send_rich
from repo.category import get_all_categories
from repo.expense import CategoryTotal, earliest_spent_at, totals_by_category
from utils import clock, currency

MONTH_PREFIX = "spend_month"
MONTH_FORMAT = "%Y-%m"

ZERO = Decimal("0")

SUBCATEGORY_MARKER = "- "
DIRECT_LABEL = "- (direct)"
TOTAL_LABEL = "Total"

CATEGORY_HEADER = "Category"
AMOUNT_HEADER = "Amount"

EMPTY = "Nothing logged in {month}."
UNAVAILABLE = "That month is not available."


@dataclass
class Row:
    """One line of the table.

    `is_branch` marks the line as a top-level category's, which is both what
    gets emphasised and what the grand total is summed from -- a subcategory's
    amount is already inside its parent's figure.
    """

    label: str
    amount: Decimal
    is_branch: bool


def _branch_rows(amounts: dict[int, Decimal], categories: list) -> list[Row]:
    """One currency's categories as table rows, biggest branch first.

    A category with nothing in the period is left out entirely, parents
    included: the report says where money went, so a row reading zero is noise.
    """
    children: dict[int, list] = {}
    for category in categories:
        if category.parent_id is not None:
            children.setdefault(category.parent_id, []).append(category)

    branches = []
    for category in categories:
        if category.parent_id is not None:
            continue

        direct = amounts.get(category.id, ZERO)
        subcategories = [
            (sub, amounts[sub.id]) for sub in children.get(category.id, []) if amounts.get(sub.id)
        ]
        total = direct + sum((amount for _, amount in subcategories), ZERO)

        if not total:
            continue

        subcategories.sort(key=lambda item: item[1], reverse=True)
        branches.append((category, direct, subcategories, total))

    branches.sort(key=lambda item: item[3], reverse=True)

    rows = []
    for category, direct, subcategories, total in branches:
        rows.append(Row(category.name, total, True))
        rows.extend(
            Row(f"{SUBCATEGORY_MARKER}{sub.name}", amount, False) for sub, amount in subcategories
        )

        if direct and subcategories:
            rows.append(Row(DIRECT_LABEL, direct, False))

    return rows


def _tables(totals: list[CategoryTotal], categories: list) -> list[tuple[str, list[Row], Decimal]]:
    """A currency, its rows and its grand total, for each currency in the period."""
    amounts: dict[str, dict[int, Decimal]] = {}
    for total in totals:
        amounts.setdefault(total.currency, {})[total.category_id] = total.total

    tables = []
    for code, per_category in amounts.items():
        rows = _branch_rows(per_category, categories)

        if rows:
            grand = sum((row.amount for row in rows if row.is_branch), ZERO)
            tables.append((code, rows, grand))

    tables.sort(key=lambda item: item[2], reverse=True)
    return tables


def _emphasised(text: str, bold: bool):
    """A cell's text, bold for a branch's line and plain for a subcategory's.

    Rich text is a plain string or a typed object, so the unemphasised case
    needs no wrapper at all.
    """
    return {"type": "bold", "text": text} if bold else text


def _table_block(rows: list[Row], code: str, caption: str, grand: Decimal) -> dict:
    """One currency's rows as a table, under a caption naming the month.

    Cell text travels as data rather than as markup, so a category called
    `<b>` needs no escaping on the way out.
    """
    cells = [
        [
            {"text": CATEGORY_HEADER, "is_header": True},
            {"text": AMOUNT_HEADER, "is_header": True, "align": "right"},
        ]
    ]

    for row in rows:
        cells.append(
            [
                {"text": _emphasised(row.label, row.is_branch)},
                {
                    "text": _emphasised(currency.format_amount(row.amount, code), row.is_branch),
                    "align": "right",
                },
            ]
        )

    cells.append(
        [
            {"text": {"type": "bold", "text": TOTAL_LABEL}},
            {
                "text": {"type": "bold", "text": currency.format_amount(grand, code)},
                "align": "right",
            },
        ]
    )

    return {
        "type": "table",
        "cells": cells,
        "caption": {"type": "bold", "text": caption},
        "is_bordered": True,
        "is_striped": True,
    }


def _month_label(month: date) -> str:
    return f"{month:%B %Y}"


def _button_label(month: date) -> str:
    """A month as a button reads it, carrying the year only when it is not this one."""
    if month.year == clock.today().year:
        return f"{month:%B}"

    return f"{month:%B %Y}"


def _blocks(chat_id: int, month: date) -> list[dict]:
    """The month's report, or a line saying it holds nothing."""
    totals = totals_by_category(chat_id, month, clock.month_end(month))
    label = _month_label(month)
    tables = _tables(totals, get_all_categories(chat_id)) if totals else []

    if not tables:
        return [{"type": "paragraph", "text": EMPTY.format(month=label)}]

    named = len(tables) > 1

    return [
        _table_block(rows, code, f"{label} · {code}" if named else label, grand)
        for code, rows, grand in tables
    ]


def _markup(chat_id: int, month: date) -> InlineKeyboardMarkup | None:
    """The months either side of this one, where there is anything to show.

    Backwards stops at the oldest expense, so the user cannot walk into empty
    months forever; forwards stops at the current month, since nothing can be
    logged past today.
    """
    buttons = []

    earliest = earliest_spent_at(chat_id)
    previous = clock.shift_month(month, -1)

    if earliest is not None and earliest < month:
        buttons.append(
            InlineKeyboardButton(
                f"‹ {_button_label(previous)}",
                callback_data=f"{MONTH_PREFIX}_{previous:{MONTH_FORMAT}}",
            )
        )

    following = clock.shift_month(month, 1)

    if following <= clock.month_start(clock.today()):
        buttons.append(
            InlineKeyboardButton(
                f"{_button_label(following)} ›",
                callback_data=f"{MONTH_PREFIX}_{following:{MONTH_FORMAT}}",
            )
        )

    return InlineKeyboardMarkup([buttons]) if buttons else None


async def _show(update: Update, context: ContextTypes.DEFAULT_TYPE, month: date) -> None:
    """Draw the month, in place when a button asked for it.

    A button press redraws the message it came from, so walking through months
    leaves one report in the chat rather than a new one per step.
    """
    chat_id = update.effective_chat.id
    blocks = _blocks(chat_id, month)
    markup = _markup(chat_id, month)

    if update.callback_query:
        await edit_rich(
            context, chat_id, update.callback_query.message.message_id, blocks, markup
        )
        return

    await send_rich(context, chat_id, blocks, markup)


async def spending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _show(update, context, clock.month_start(clock.today()))


async def month_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Redraw the report for the month a button named.

    The month is parsed rather than trusted: the pattern admits dates that do
    not exist, like a thirteenth month, and a button is an input the user can
    replay at any time.
    """
    value = update.callback_query.data.removeprefix(f"{MONTH_PREFIX}_")

    try:
        month = datetime.strptime(value, MONTH_FORMAT).date()
    except ValueError:
        await update.callback_query.answer(UNAVAILABLE, show_alert=True)
        return

    await update.callback_query.answer()
    await _show(update, context, month)


spending_handler = CommandHandler("spending", spending)
spending_month_handler = CallbackQueryHandler(
    month_chosen, pattern=rf"^{MONTH_PREFIX}_\d{{4}}-\d{{2}}$"
)
