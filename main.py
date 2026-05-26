import logging

from config import BOT_TOKEN
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from database import SessionLocal, engine
from models.models import Base, Expense, User

from handlers.category import add_category_handler
from handlers.expense import add_expense_handler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


def register_user(chat_id: int, name: str):
    with SessionLocal() as session:
        user = User(chat_id=chat_id, name=name)
        session.add(user)
        session.commit()


def add_expense(
    chat_id: int,
    amount: float,
    category: str,
    description: str | None = None,
    currency: str = "CAD",
):
    with SessionLocal() as session:
        expense = Expense(
            chat_id=chat_id,
            amount=amount,
            category=category,
            description=description,
            currency=currency,
        )
        session.add(expense)
        session.commit()


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
    application.run_polling()
