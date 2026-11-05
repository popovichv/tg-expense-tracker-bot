"""An expense from one typed line: `12.50 coffee`.

/add_expense asks five questions -- category, subcategory, amount,
description, date -- which is four too many for something done several times a
day. Here the amount and the description are read off the message, the date is
today, and the only thing left to ask is the one thing the bot cannot work out
for itself.

Only a message beginning with a digit is treated as an attempt, so ordinary
chatter is left alone rather than answered with a category keyboard. One that
begins with a digit but carries no usable amount is told how it should read,
since silence there looks like a bot that has stopped working.

The flow reenters, so a second line typed while the keyboard is still up
replaces the first rather than being swallowed: the amount on screen is
always the one last sent.
"""

import html

from telegram import InlineKeyboardButton, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from handlers.expense import format_expense_blocks
from handlers.manage_expenses import edit_markup
from handlers.pickers import category_markup, chosen_id
from handlers.prompts import clear_prompts, track_prompt
from handlers.rich import edit_rich
from handlers.summary import MISSING_DESCRIPTION, long_date
from repo.category import get_subcategories, get_top_level_categories
from repo.expense import add_expense as add_expense_to_db
from repo.user import get_currency
from utils import clock, currency
from utils.amounts import split_amount

TRIGGER = r"^\s*\d"

CATEGORY_PREFIX = "qck_cat"
USE_PARENT = "qck_parent"
CANCEL = "qck_cancel"

CANCEL_BUTTON = InlineKeyboardButton("Cancel", callback_data=CANCEL)

CHOOSE_CATEGORY = "Choose a category:"
CHOOSE_SUBCATEGORY = "Choose a subcategory:"

HINT = (
    "I could not read an amount there. Send an expense as an amount and an "
    "optional note, like <code>12.50 coffee</code>."
)
NO_CATEGORIES = "You have no categories yet. Use /add_category to create one first."
CANCELLED = "Expense creation cancelled."
STALE = "That line is no longer being logged. Send the amount again."

CHOOSING_CATEGORY = 1
CHOOSING_SUBCATEGORY = 2


async def _still_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Whether what this keyboard was drawn for is still waiting to be written.

    The flows share `user_data`, so starting /add_expense or /manage_expenses
    on top of a keyboard left standing here replaces what it was holding. The
    button would then write an expense from whatever the other flow happened
    to leave behind, so it says it has gone stale instead -- the same answer
    the bot gives for any button that outlived its flow.
    """
    if "amount" in context.user_data and "category_names" in context.user_data:
        return True

    await update.callback_query.answer(STALE, show_alert=True)
    return False


def _screen(context: ContextTypes.DEFAULT_TYPE, chat_id: int, question: str) -> str:
    """What was read from the message, above the question still outstanding.

    It is shown back because it was parsed rather than typed into a prompt that
    asked for it: seeing `$15.50` after sending "10 + 5 lunch" is how the user
    knows the sum was understood, before anything is written. The date is shown
    for the same reason though nobody supplied it -- it is assumed, and an
    assumption the user cannot see is one they find out about later, on a
    report. Labelled the way an expense is labelled everywhere else, so this
    screen and the confirmation that replaces it read as one thing rather than
    two.
    """
    code = get_currency(chat_id)
    amount = currency.format_amount(context.user_data["amount"], code)
    description = context.user_data.get("description") or MISSING_DESCRIPTION

    return (
        f"<b>Description:</b> {html.escape(description)}\n"
        f"<b>Amount:</b> {html.escape(amount)}\n"
        f"<b>Date:</b> {html.escape(long_date(clock.today()))}\n\n"
        f"{question}"
    )


async def quick_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Read the line, then ask the only question left."""
    parsed = split_amount(update.message.text)

    if parsed is None:
        await update.message.reply_text(HINT, parse_mode="HTML")
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    categories = get_top_level_categories(chat_id)

    if not categories:
        await update.message.reply_text(NO_CATEGORIES)
        return ConversationHandler.END

    amount, description = parsed

    await clear_prompts(update, context)
    context.user_data.clear()
    context.user_data["amount"] = amount
    context.user_data["description"] = description
    context.user_data["category_names"] = {cat.id: cat.name for cat in categories}

    prompt = await update.message.reply_text(
        _screen(context, chat_id, CHOOSE_CATEGORY),
        parse_mode="HTML",
        reply_markup=category_markup(categories, CATEGORY_PREFIX, [CANCEL_BUTTON]),
    )
    track_prompt(context, prompt)
    return CHOOSING_CATEGORY


async def _log(update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: int):
    """Write the expense, leaving the confirmation where the keyboard was.

    The confirmation is the one /add_expense ends on, Edit button included, so
    a date that is not today or a description that came out wrong is two taps
    away rather than a reason to have asked up front.
    """
    chat_id = update.effective_chat.id
    data = context.user_data
    data["category_name"] = data["category_names"][category_id]

    spent_at = clock.today()
    code = get_currency(chat_id)

    expense = add_expense_to_db(
        chat_id=chat_id,
        category_id=category_id,
        amount=data["amount"],
        description=data.get("description"),
        spent_at=spent_at,
        currency=code,
    )

    await edit_rich(
        context,
        chat_id,
        update.callback_query.message.message_id,
        format_expense_blocks(data, spent_at, code),
        edit_markup(expense.id),
    )

    await clear_prompts(update, context, keep=update.callback_query.message.message_id)
    context.user_data.clear()
    return ConversationHandler.END


async def category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log it, unless the category chosen has subcategories to choose between."""
    if not await _still_pending(update, context):
        return ConversationHandler.END

    await update.callback_query.answer()

    category_id = chosen_id(update)
    chat_id = update.effective_chat.id
    subcategories = get_subcategories(category_id, chat_id)

    if not subcategories:
        return await _log(update, context, category_id)

    context.user_data["category_names"].update(
        {cat.id: cat.name for cat in subcategories}
    )
    context.user_data["parent_category_id"] = category_id

    parent_name = context.user_data["category_names"][category_id]
    use_parent = [
        InlineKeyboardButton(f"Use '{parent_name}' directly", callback_data=USE_PARENT)
    ]

    await update.callback_query.edit_message_text(
        _screen(context, chat_id, CHOOSE_SUBCATEGORY),
        parse_mode="HTML",
        reply_markup=category_markup(
            subcategories, CATEGORY_PREFIX, [CANCEL_BUTTON], extra_row=use_parent
        ),
    )
    return CHOOSING_SUBCATEGORY


async def subcategory_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _still_pending(update, context):
        return ConversationHandler.END

    await update.callback_query.answer()
    return await _log(update, context, chosen_id(update))


async def parent_category_used(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _still_pending(update, context):
        return ConversationHandler.END

    await update.callback_query.answer()
    return await _log(update, context, context.user_data["parent_category_id"])


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Drop what was read, leaving nothing written."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(CANCELLED)
        await clear_prompts(
            update, context, keep=update.callback_query.message.message_id
        )
    else:
        await update.message.reply_text(CANCELLED)
        await clear_prompts(update, context)

    context.user_data.clear()
    return ConversationHandler.END


quick_expense_handler = ConversationHandler(
    entry_points=[
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(TRIGGER), quick_expense
        )
    ],
    states={
        CHOOSING_CATEGORY: [
            CallbackQueryHandler(category_chosen, pattern=rf"^{CATEGORY_PREFIX}_\d+$"),
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        ],
        CHOOSING_SUBCATEGORY: [
            CallbackQueryHandler(subcategory_chosen, pattern=rf"^{CATEGORY_PREFIX}_\d+$"),
            CallbackQueryHandler(parent_category_used, pattern=f"^{USE_PARENT}$"),
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True,
)
