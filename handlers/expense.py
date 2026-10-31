from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from handlers.manage_expenses import edit_markup
from handlers.pickers import category_markup, chosen_id
from handlers.prompts import clear_prompts, track_prompt
from handlers.summary import expense_summary
from repo.user import get_currency
from utils import clock
from utils.amounts import parse_amount
from repo.category import get_top_level_categories, get_subcategories
from repo.expense import add_expense as add_expense_to_db

# Callbacks
CATEGORY_PREFIX = "exp_cat"

CANCEL = "exp_cancel"
SKIP_DESC = "exp_skip_desc"
TODAY = "exp_today"
USE_PARENT = "exp_use_parent"

CANCEL_BUTTON = InlineKeyboardButton("Cancel", callback_data=CANCEL)
CANCEL_MARKUP = InlineKeyboardMarkup([[CANCEL_BUTTON]])

AMOUNT_PROMPT = "Enter the amount:"
DATE_PROMPT = "When was this expense? Enter a date (YYYY-MM-DD) or tap Today:"

# States
CHOOSING_CATEGORY = 1
CHOOSING_SUBCATEGORY = 2
TYPING_AMOUNT = 3
TYPING_DESCRIPTION = 4
CHOOSING_DATE = 5


async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    categories = get_top_level_categories(chat_id)

    if not categories:
        await update.message.reply_text(
            "You have no categories yet. Use /add_category to create one first."
        )
        return ConversationHandler.END

    context.user_data["category_names"] = {cat.id: cat.name for cat in categories}

    prompt = await update.message.reply_text(
        "Choose a category:",
        reply_markup=category_markup(categories, CATEGORY_PREFIX, [CANCEL_BUTTON]),
    )
    track_prompt(context, prompt)
    return CHOOSING_CATEGORY


async def top_category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    category_id = chosen_id(update)
    chat_id = update.effective_chat.id
    subcategories = get_subcategories(category_id, chat_id)

    if subcategories:
        context.user_data["category_names"].update({cat.id: cat.name for cat in subcategories})
        context.user_data["parent_category_id"] = category_id

        parent_name = context.user_data["category_names"][category_id]
        use_parent = [
            InlineKeyboardButton(f"Use '{parent_name}' directly", callback_data=USE_PARENT)
        ]

        await update.callback_query.edit_message_text(
            "Choose a subcategory:",
            reply_markup=category_markup(
                subcategories, CATEGORY_PREFIX, [CANCEL_BUTTON], extra_row=use_parent
            ),
        )
        return CHOOSING_SUBCATEGORY

    context.user_data["category_id"] = category_id
    context.user_data["category_name"] = context.user_data["category_names"][category_id]

    await update.callback_query.edit_message_text(AMOUNT_PROMPT, reply_markup=CANCEL_MARKUP)
    return TYPING_AMOUNT


async def parent_category_used(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    category_id = context.user_data["parent_category_id"]
    context.user_data["category_id"] = category_id
    context.user_data["category_name"] = context.user_data["category_names"][category_id]

    await update.callback_query.edit_message_text(AMOUNT_PROMPT, reply_markup=CANCEL_MARKUP)
    return TYPING_AMOUNT


async def subcategory_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    category_id = chosen_id(update)
    context.user_data["category_id"] = category_id
    context.user_data["category_name"] = context.user_data["category_names"][category_id]

    await update.callback_query.edit_message_text(AMOUNT_PROMPT, reply_markup=CANCEL_MARKUP)
    return TYPING_AMOUNT


async def amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount = parse_amount(update.message.text)

    if amount is None:
        prompt = await update.message.reply_text(
            "Please enter a valid positive number (e.g. 12.50):",
            reply_markup=CANCEL_MARKUP,
        )
        track_prompt(context, prompt)
        return TYPING_AMOUNT

    context.user_data["amount"] = amount

    keyboard = [
        [InlineKeyboardButton("Skip", callback_data=SKIP_DESC)],
        [CANCEL_BUTTON],
    ]

    prompt = await update.message.reply_text(
        "Enter a description (or skip):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    track_prompt(context, prompt)
    return TYPING_DESCRIPTION


async def description_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text.strip()

    keyboard = [
        [InlineKeyboardButton("Today", callback_data=TODAY)],
        [CANCEL_BUTTON],
    ]

    prompt = await update.message.reply_text(
        DATE_PROMPT,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    track_prompt(context, prompt)
    return CHOOSING_DATE


async def description_skipped(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    context.user_data["description"] = None

    keyboard = [
        [InlineKeyboardButton("Today", callback_data=TODAY)],
        [CANCEL_BUTTON],
    ]

    await update.callback_query.edit_message_text(
        DATE_PROMPT,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_DATE


def format_expense_summary(data, spent_at, code: str) -> str:
    """Build the confirmation, in the layout an expense is shown in anywhere."""
    return expense_summary(
        title="Expense Recorded",
        category=data.get("category_name") or "",
        description=data.get("description"),
        amount=data["amount"],
        code=code,
        spent_at=spent_at,
    )


async def date_set_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    data = context.user_data
    spent_at = clock.today()
    code = get_currency(update.effective_chat.id)

    expense = add_expense_to_db(
        chat_id=update.effective_chat.id,
        category_id=data["category_id"],
        amount=data["amount"],
        description=data.get("description"),
        spent_at=spent_at,
        currency=code,
    )

    await update.callback_query.edit_message_text(
        format_expense_summary(data, spent_at, code),
        parse_mode="HTML",
        reply_markup=edit_markup(expense.id),
    )

    await clear_prompts(update, context, keep=update.callback_query.message.message_id)
    context.user_data.clear()
    return ConversationHandler.END


async def date_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        spent_at = date.fromisoformat(update.message.text.strip())
    except ValueError:
        prompt = await update.message.reply_text(
            "Invalid date format. Please use YYYY-MM-DD (e.g. 2024-05-20):",
            reply_markup=CANCEL_MARKUP,
        )
        track_prompt(context, prompt)
        return CHOOSING_DATE

    data = context.user_data
    code = get_currency(update.effective_chat.id)

    expense = add_expense_to_db(
        chat_id=update.effective_chat.id,
        category_id=data["category_id"],
        amount=data["amount"],
        description=data.get("description"),
        spent_at=spent_at,
        currency=code,
    )

    await update.message.reply_text(
        format_expense_summary(data, spent_at, code),
        parse_mode="HTML",
        reply_markup=edit_markup(expense.id),
    )

    await clear_prompts(update, context)
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Expense creation cancelled."

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text)
        await clear_prompts(update, context, keep=update.callback_query.message.message_id)
    else:
        await update.message.reply_text(text)
        await clear_prompts(update, context)

    context.user_data.clear()
    return ConversationHandler.END


add_expense_handler = ConversationHandler(
    entry_points=[CommandHandler("add_expense", add_expense)],
    states={
        CHOOSING_CATEGORY: [
            CallbackQueryHandler(top_category_chosen, pattern=rf"^{CATEGORY_PREFIX}_\d+$"),
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        ],
        CHOOSING_SUBCATEGORY: [
            CallbackQueryHandler(subcategory_chosen, pattern=rf"^{CATEGORY_PREFIX}_\d+$"),
            CallbackQueryHandler(parent_category_used, pattern=f"^{USE_PARENT}$"),
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        ],
        TYPING_AMOUNT: [
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, amount_received),
        ],
        TYPING_DESCRIPTION: [
            CallbackQueryHandler(description_skipped, pattern=f"^{SKIP_DESC}$"),
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, description_received),
        ],
        CHOOSING_DATE: [
            CallbackQueryHandler(date_set_today, pattern=f"^{TODAY}$"),
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, date_received),
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
    ],
)
