import html
from datetime import date
from decimal import Decimal, InvalidOperation

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from handlers.prompts import clear_prompts, track_prompt
from repo.category import get_top_level_categories, get_subcategories
from repo.expense import add_expense as add_expense_to_db

# Callbacks
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


def build_category_keyboard(categories, include_cancel=True):
    buttons = [
        InlineKeyboardButton(cat.name, callback_data=f"exp_cat_{cat.id}") for cat in categories
    ]
    keyboard = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    if include_cancel:
        keyboard.append([CANCEL_BUTTON])
    return keyboard


async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    categories = get_top_level_categories(chat_id)

    if not categories:
        await update.message.reply_text(
            "You have no categories yet. Use /add_category to create one first."
        )
        return ConversationHandler.END

    context.user_data["category_names"] = {cat.id: cat.name for cat in categories}

    keyboard = build_category_keyboard(categories)
    prompt = await update.message.reply_text(
        "Choose a category:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    track_prompt(context, prompt)
    return CHOOSING_CATEGORY


async def top_category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    category_id = int(update.callback_query.data.split("_")[2])
    chat_id = update.effective_chat.id
    subcategories = get_subcategories(category_id, chat_id)

    if subcategories:
        context.user_data["category_names"].update({cat.id: cat.name for cat in subcategories})
        context.user_data["parent_category_id"] = category_id

        keyboard = build_category_keyboard(subcategories, include_cancel=False)
        parent_name = context.user_data["category_names"][category_id]
        keyboard.append(
            [InlineKeyboardButton(f"Use '{parent_name}' directly", callback_data=USE_PARENT)]
        )
        keyboard.append([CANCEL_BUTTON])
        await update.callback_query.edit_message_text(
            "Choose a subcategory:",
            reply_markup=InlineKeyboardMarkup(keyboard),
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

    category_id = int(update.callback_query.data.split("_")[2])
    context.user_data["category_id"] = category_id
    context.user_data["category_name"] = context.user_data["category_names"][category_id]

    await update.callback_query.edit_message_text(AMOUNT_PROMPT, reply_markup=CANCEL_MARKUP)
    return TYPING_AMOUNT


async def amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", ".")
    amounts = [a.strip() for a in text.split("+")]
    try:
        amount = sum(Decimal(a) for a in amounts)
        if not amount.is_finite() or amount <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
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


def format_expense_summary(data, spent_at) -> str:
    """Build the confirmation message, escaping anything the user typed.

    Category names and descriptions are user supplied, so a name containing
    `<` would otherwise make Telegram reject the whole message as malformed
    HTML and the confirmation would never arrive.
    """
    category = html.escape(data.get("category_name") or "")
    description = html.escape(data.get("description") or "N/A")

    return (
        f"<b>Expense Recorded</b>\n"
        f"----------------------------\n"
        f"<b>Category:</b> {category}\n"
        f"<b>Description:</b> {description}\n"
        f"<b>Amount:</b> ${data['amount']:.2f}\n"
        f"<b>Date:</b> {spent_at}"
    )


async def date_set_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    data = context.user_data
    spent_at = date.today()

    add_expense_to_db(
        chat_id=update.effective_chat.id,
        category_id=data["category_id"],
        amount=data["amount"],
        description=data.get("description"),
        spent_at=spent_at,
    )

    await update.callback_query.edit_message_text(
        format_expense_summary(data, spent_at),
        parse_mode="HTML",
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
    add_expense_to_db(
        chat_id=update.effective_chat.id,
        category_id=data["category_id"],
        amount=data["amount"],
        description=data.get("description"),
        spent_at=spent_at,
    )

    await update.message.reply_text(
        format_expense_summary(data, spent_at),
        parse_mode="HTML",
    )

    await clear_prompts(update, context)
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Expense creation cancelled."

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text)
    else:
        await update.message.reply_text(text)

    context.user_data.clear()
    return ConversationHandler.END


add_expense_handler = ConversationHandler(
    entry_points=[CommandHandler("add_expense", add_expense)],
    states={
        CHOOSING_CATEGORY: [
            CallbackQueryHandler(top_category_chosen, pattern=r"^exp_cat_\d+$"),
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        ],
        CHOOSING_SUBCATEGORY: [
            CallbackQueryHandler(subcategory_chosen, pattern=r"^exp_cat_\d+$"),
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
