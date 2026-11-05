"""The category tree, sent as a rich message table.

A plain-text tree of short names comes out as a tall narrow column, because
Telegram sizes a bubble to its widest line. A rich message table (Bot API
10.1) puts the subcategories beside their parent instead and lets the client
size the columns.

Cell text travels as data rather than as markup, so a category named `<b>`
or `a | b` needs no escaping.

The title rides on the table's own caption: no InputRichBlock text block has
an alignment field, so a `paragraph` cannot be centered, and the one block
that centers its text, `pullquote`, carries quotation styling instead of
normal text.
"""

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from handlers.rich import send_rich

from repo.category import get_top_level_categories, get_subcategories

TITLE = "Your Categories"
SEPARATOR = ", "
NO_SUBCATEGORIES = "—"


def _categories_table(rows: list[tuple[str, list[str]]]) -> dict:
    cells = [
        [
            {"text": "Category", "is_header": True},
            {"text": "Subcategories", "is_header": True},
        ]
    ]

    for name, subcategories in rows:
        cells.append(
            [
                {"text": name},
                {"text": SEPARATOR.join(subcategories) or NO_SUBCATEGORIES},
            ]
        )

    return {
        "type": "table",
        "cells": cells,
        "caption": {"type": "bold", "text": TITLE},
        "is_bordered": True,
        "is_striped": True,
    }


async def list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    top_level = get_top_level_categories(chat_id)

    if not top_level:
        await update.message.reply_text(
            "You have no categories yet. Use /add_category to create one."
        )
        return

    rows = [
        (category.name, [sub.name for sub in get_subcategories(category.id, chat_id)])
        for category in top_level
    ]

    await send_rich(context, chat_id, [_categories_table(rows)])


list_categories_handler = CommandHandler("list_categories", list_categories)
