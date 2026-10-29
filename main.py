import logging

from config import BOT_TOKEN
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from sqlalchemy import text
from database import SessionLocal, engine
from models.models import Base, User

from handlers.category import add_category_handler
from handlers.expense import add_expense_handler
from handlers.list_categories import list_categories_handler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


async def keep_alive_db(context: ContextTypes.DEFAULT_TYPE):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.warning("DB keep-alive ping failed: %s", e)


def register_user(chat_id: int, name: str):
    with SessionLocal() as session:
        user = User(chat_id=chat_id, name=name)
        session.add(user)
        session.commit()


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

    register_user(chat_id, name)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Hi {name}! You have been saved in the database with chat ID: {chat_id}",
    )


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    start_handler = CommandHandler("start", start)
    application.add_handler(start_handler)
    application.add_handler(add_category_handler)
    application.add_handler(add_expense_handler)
    application.add_handler(list_categories_handler)
    application.add_handler(CommandHandler("cancel", stale_cancel))
    application.add_handler(CallbackQueryHandler(stale_cancel, pattern=r"^(cancel|exp_cancel)$"))
    application.job_queue.run_repeating(keep_alive_db, interval=180, first=10)
    application.run_polling()
