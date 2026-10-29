from decimal import Decimal

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
from repo.user import get_currency, set_currency
from utils import currency

CANCEL = "cur_cancel"

CANCEL_BUTTON = InlineKeyboardButton("Cancel", callback_data=CANCEL)
CANCEL_MARKUP = InlineKeyboardMarkup([[CANCEL_BUTTON]])

TYPING_CURRENCY = 1

SAMPLE = Decimal("12.50")


def prompt_text(current: str) -> str:
    return (
        f"Your currency is {current} ({currency.format_amount(SAMPLE, current)}).\n"
        "Send a three-letter code to change it, for example USD, EUR or PLN:"
    )


def confirmation_text(code: str) -> str:
    return (
        f"Currency set to {code}. New expenses will look like "
        f"{currency.format_amount(SAMPLE, code)}.\n"
        "Expenses you already recorded keep the currency they were saved with."
    )


async def set_currency_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if context.args:
        return await apply_code(update, context, " ".join(context.args))

    prompt = await update.message.reply_text(
        prompt_text(get_currency(chat_id)),
        reply_markup=CANCEL_MARKUP,
    )
    track_prompt(context, prompt)
    return TYPING_CURRENCY


async def apply_code(update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str):
    """Validate and store a code, re-prompting if it is not a currency code."""
    code = currency.normalize(raw)

    if code is None:
        prompt = await update.message.reply_text(
            "That does not look like a currency code. Send three letters, "
            "for example USD, EUR or PLN:",
            reply_markup=CANCEL_MARKUP,
        )
        track_prompt(context, prompt)
        return TYPING_CURRENCY

    set_currency(update.effective_chat.id, code)
    await update.message.reply_text(confirmation_text(code))

    await clear_prompts(update, context)
    context.user_data.clear()
    return ConversationHandler.END


async def currency_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await apply_code(update, context, update.message.text)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Currency unchanged."

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text)
        await clear_prompts(update, context, keep=update.callback_query.message.message_id)
    else:
        await update.message.reply_text(text)
        await clear_prompts(update, context)

    context.user_data.clear()
    return ConversationHandler.END


set_currency_handler = ConversationHandler(
    entry_points=[CommandHandler("set_currency", set_currency_command)],
    states={
        TYPING_CURRENCY: [
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, currency_received),
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
    ],
)
