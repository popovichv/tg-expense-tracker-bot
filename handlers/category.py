from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from repo.category import get_top_level_categories, add_category as add_category_to_db
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Callbacks
TOP_CATEGORY = "top_level"
SUB_CATEGORY = "with_parent"
CANCEL = "cancel"

# States
CHOOSING_TYPE = 1
CHOOSING_PARENT = 2
TYPING_NAME = 3


async def add_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Top-level category", callback_data=TOP_CATEGORY)],
        [InlineKeyboardButton("Subcategory", callback_data=SUB_CATEGORY)],
        [InlineKeyboardButton("Cancel", callback_data=CANCEL)],
    ]

    await update.message.reply_text(
        "What kind of category do you want to add?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_TYPE


async def chosen_top_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    context.user_data["parent_id"] = None

    await update.callback_query.edit_message_text("Please send me the category name.")
    return TYPING_NAME


async def chosen_sub_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    chat_id = update.effective_chat.id
    user_categories = get_top_level_categories(chat_id)

    if not user_categories:
        await update.callback_query.edit_message_text(
            "You have no top-level categories yet. Create one first."
        )
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton(cat.name, callback_data=str(cat.id))] for cat in user_categories
    ]
    keyboard.append([InlineKeyboardButton("Cancel", callback_data=CANCEL)])

    await update.callback_query.edit_message_text(
        "Choose a parent category:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_PARENT


async def chosen_parent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()

    parent_id = int(update.callback_query.data)
    context.user_data["parent_id"] = parent_id

    await update.callback_query.edit_message_text("Please send me the subcategory name.")
    return TYPING_NAME


async def received_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    parent_id = context.user_data.get("parent_id")
    chat_id = update.effective_chat.id

    add_category_to_db(name=name, chat_id=chat_id, parent_id=parent_id)

    label = "Category" if parent_id is None else "Subcategory"
    await update.message.reply_text(f"{label} '{name}' added.")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    await update.callback_query.edit_message_text("Category creation cancelled.")
    return ConversationHandler.END


add_category_handler = ConversationHandler(
    entry_points=[CommandHandler("add_category", add_category)],
    states={
        CHOOSING_TYPE: [
            CallbackQueryHandler(chosen_top_category, pattern=f"^{TOP_CATEGORY}$"),
            CallbackQueryHandler(chosen_sub_category, pattern=f"^{SUB_CATEGORY}$"),
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        ],
        CHOOSING_PARENT: [
            CallbackQueryHandler(chosen_parent, pattern=r"^\d+$"),
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        ],
        TYPING_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, received_name),
        ],
    },
    fallbacks=[CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$")],
)
