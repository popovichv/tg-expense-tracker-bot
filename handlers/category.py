from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from handlers.pickers import category_markup, chosen_id
from handlers.prompts import clear_prompts, track_prompt
from repo.category import (
    add_category as add_category_to_db,
    find_duplicate,
    get_top_level_categories,
)
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

PARENT_PREFIX = "cat_parent"

CANCEL_BUTTON = InlineKeyboardButton("Cancel", callback_data=CANCEL)
CANCEL_MARKUP = InlineKeyboardMarkup([[CANCEL_BUTTON]])

# States
CHOOSING_TYPE = 1
CHOOSING_PARENT = 2
TYPING_NAME = 3


async def add_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Top-level category", callback_data=TOP_CATEGORY)],
        [InlineKeyboardButton("Subcategory", callback_data=SUB_CATEGORY)],
        [CANCEL_BUTTON],
    ]

    prompt = await update.message.reply_text(
        "What kind of category do you want to add?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    track_prompt(context, prompt)
    return CHOOSING_TYPE


async def chosen_top_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    context.user_data["parent_id"] = None

    await update.callback_query.edit_message_text(
        "Please send me the category name.",
        reply_markup=CANCEL_MARKUP,
    )
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

    await update.callback_query.edit_message_text(
        "Choose a parent category:",
        reply_markup=category_markup(user_categories, PARENT_PREFIX, [CANCEL_BUTTON]),
    )
    return CHOOSING_PARENT


async def chosen_parent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()

    context.user_data["parent_id"] = chosen_id(update)

    await update.callback_query.edit_message_text(
        "Please send me the subcategory name.",
        reply_markup=CANCEL_MARKUP,
    )
    return TYPING_NAME


async def received_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    parent_id = context.user_data.get("parent_id")
    chat_id = update.effective_chat.id

    if not name:
        prompt = await update.message.reply_text(
            "A category needs a name. Send one:",
            reply_markup=CANCEL_MARKUP,
        )
        track_prompt(context, prompt)
        return TYPING_NAME

    existing = find_duplicate(name, chat_id, parent_id)
    if existing is not None:
        where = "at the top level" if parent_id is None else "under that category"
        prompt = await update.message.reply_text(
            f"'{existing.name}' already exists {where}. Send a different name:",
            reply_markup=CANCEL_MARKUP,
        )
        track_prompt(context, prompt)
        return TYPING_NAME

    add_category_to_db(name=name, chat_id=chat_id, parent_id=parent_id)

    label = "Category" if parent_id is None else "Subcategory"
    await update.message.reply_text(f"{label} '{name}' added.")

    await clear_prompts(update, context)
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Category creation cancelled."

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text)
        await clear_prompts(update, context, keep=update.callback_query.message.message_id)
    else:
        await update.message.reply_text(text)
        await clear_prompts(update, context)

    context.user_data.clear()
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
            CallbackQueryHandler(chosen_parent, pattern=rf"^{PARENT_PREFIX}_\d+$"),
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        ],
        TYPING_NAME: [
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, received_name),
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
    ],
)
