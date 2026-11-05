"""Sending and editing rich messages, which the library has no wrapper for.

python-telegram-bot 22.8 targets Bot API 10.0, so both sendRichMessage and
editMessageText's `rich_message` parameter go through do_api_request, the
library's escape hatch for newer methods. One module knows that, rather than
every screen that wants a table.

Blocks travel as data rather than as markup, so nothing passed through here
needs escaping: a category called `<b>` arrives as those three characters.
"""

from telegram import InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes

NO_KEYBOARD = {"inline_keyboard": []}


async def send_rich(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    blocks: list[dict],
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message:
    """Post a rich message, returning it the way the library's senders do.

    Deserialized into a Message rather than left as raw JSON, because a caller
    that posts a screen has to remember its id to tidy it away afterwards.
    """
    api_kwargs = {"chat_id": chat_id, "rich_message": {"blocks": blocks}}

    if reply_markup is not None:
        api_kwargs["reply_markup"] = reply_markup.to_dict()

    return await context.bot.do_api_request(
        "sendRichMessage", api_kwargs=api_kwargs, return_type=Message
    )


async def edit_rich(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    blocks: list[dict],
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Replace what a message holds, keyboard included.

    The keyboard is always sent: left out, Telegram keeps whatever was on the
    message, so a screen that has finished with its buttons would keep them.
    """
    await context.bot.do_api_request(
        "editMessageText",
        api_kwargs={
            "chat_id": chat_id,
            "message_id": message_id,
            "rich_message": {"blocks": blocks},
            "reply_markup": reply_markup.to_dict() if reply_markup else NO_KEYBOARD,
        },
    )
