import logging

from config import BOT_TOKEN
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    TypeHandler,
)

from repo.user import get_or_create_user

from handlers.category import add_category_handler
from handlers.expense import add_expense_handler
from handlers.list_categories import list_categories_handler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.WARNING,
)

for _app_logger in ("__main__", "handlers", "models", "repo", "database"):
    logging.getLogger(_app_logger).setLevel(logging.INFO)

logger = logging.getLogger(__name__)


async def ensure_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register the chat before any handler writes a row keyed on it.

    Runs ahead of the command handlers for every update, so a user who never
    sent /start does not hit a foreign key violation. Each chat is looked up
    once per process. The `user_created` flag is rewritten on every update and
    means "this update registered the chat", which is what `start` reports on.
    """
    chat = update.effective_chat
    user = update.effective_user

    if chat is None or user is None:
        return

    known_chats = context.bot_data.setdefault("known_chats", set())
    if chat.id in known_chats:
        context.chat_data["user_created"] = False
        return

    _, created = get_or_create_user(chat.id, user.first_name)
    known_chats.add(chat.id)
    context.chat_data["user_created"] = created


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log an unhandled handler exception and tell the user, rather than going quiet."""
    logger.error("Unhandled exception while processing an update", exc_info=context.error)

    if not isinstance(update, Update) or update.effective_chat is None:
        return

    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Something went wrong. Please try again.",
        )
    except TelegramError:
        pass


async def stale_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /cancel and Cancel buttons left over from a finished conversation.

    Registered after the conversation handlers, so an active conversation always
    cancels itself first and this only catches what nothing else claimed.
    """
    if update.callback_query:
        await update.callback_query.answer("This action is no longer active.")
        return

    await update.message.reply_text("Nothing to cancel.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    name = update.effective_user.first_name

    if context.chat_data.pop("user_created", False):
        text = (
            f"Hi {name}! You have been saved in the database with chat ID: {chat_id}\n"
            "I have added some starter categories — see /list_categories."
        )
    else:
        text = f"Welcome back, {name}! You are already registered."

    await context.bot.send_message(chat_id=chat_id, text=text)


if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(TypeHandler(Update, ensure_user), group=-1)

    start_handler = CommandHandler("start", start)
    application.add_handler(start_handler)
    application.add_handler(add_category_handler)
    application.add_handler(add_expense_handler)
    application.add_handler(list_categories_handler)
    application.add_handler(CommandHandler("cancel", stale_cancel))
    application.add_handler(CallbackQueryHandler(stale_cancel, pattern=r"^(cancel|exp_cancel)$"))
    application.add_error_handler(on_error)
    application.run_polling()
