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

from repo.category import get_top_level_categories, get_subcategories
from repo.expense import add_expense as add_expense_to_db

# Callbacks
CANCEL = "exp_cancel"
SKIP_DESC = "exp_skip_desc"
TODAY = "exp_today"

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
        keyboard.append([InlineKeyboardButton("Cancel", callback_data=CANCEL)])
    return keyboard


async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    categories = get_top_level_categories(chat_id)

    if not categories:
        await update.message.reply_text(
            "You have no categories yet. Use /add_category to create one first."
        )
        return ConversationHandler.END

    keyboard = build_category_keyboard(categories)
    await update.message.reply_text(
        "Choose a category:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_CATEGORY


async def top_category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    category_id = int(update.callback_query.data.split("_")[2])
    chat_id = update.effective_chat.id
    subcategories = get_subcategories(category_id, chat_id)

    if subcategories:
        keyboard = build_category_keyboard(subcategories)
        await update.callback_query.edit_message_text(
            "Choose a subcategory:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return CHOOSING_SUBCATEGORY

    context.user_data["category_id"] = category_id

    await update.callback_query.edit_message_text("Enter the amount:")
    return TYPING_AMOUNT


async def subcategory_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    context.user_data["category_id"] = int(update.callback_query.data.split("_")[2])

    await update.callback_query.edit_message_text("Enter the amount:")
    return TYPING_AMOUNT


async def amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", ".")
    amounts = [a.strip() for a in text.split("+")]
    try:
        for i in range(len(amounts)):
            amounts[i] = float(amounts[i])

        amount = sum(amounts)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid positive number (e.g. 12.50):")
        return TYPING_AMOUNT

    context.user_data["amount"] = amount

    keyboard = [[InlineKeyboardButton("Skip", callback_data=SKIP_DESC)]]

    await update.message.reply_text(
        "Enter a description (or skip):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return TYPING_DESCRIPTION


async def description_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text.strip()

    keyboard = [[InlineKeyboardButton("Today", callback_data=TODAY)]]

    await update.message.reply_text(
        "When was this expense? Enter a date (YYYY-MM-DD) or tap Today:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_DATE


async def description_skipped(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    context.user_data["description"] = None

    keyboard = [[InlineKeyboardButton("Today", callback_data=TODAY)]]

    await update.callback_query.edit_message_text(
        "When was this expense? Enter a date (YYYY-MM-DD) or tap Today:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_DATE


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
        f"Expense saved!\nAmount: {data['amount']:.2f}\nDate: {spent_at}"
    )
    context.user_data.clear()
    return ConversationHandler.END


async def date_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        spent_at = date.fromisoformat(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            "Invalid date format. Please use YYYY-MM-DD (e.g. 2024-05-20):"
        )
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
        f"Expense saved!\nAmount: {data['amount']:.2f}\nDate: {spent_at}"
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    await update.callback_query.edit_message_text("Expense creation cancelled.")
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
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        ],
        TYPING_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, amount_received),
        ],
        TYPING_DESCRIPTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, description_received),
            CallbackQueryHandler(description_skipped, pattern=f"^{SKIP_DESC}$"),
        ],
        CHOOSING_DATE: [
            CallbackQueryHandler(date_set_today, pattern=f"^{TODAY}$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, date_received),
        ],
    },
    fallbacks=[CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$")],
)
