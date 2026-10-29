from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes


def track_prompt(context: ContextTypes.DEFAULT_TYPE, message) -> None:
    """Remember a prompt the bot sent, so it can be tidied away at the end.

    Prompts the bot edits in place keep their original message id and are
    already tracked from when they were first sent.
    """
    if message is not None:
        context.user_data.setdefault("prompt_ids", []).append(message.message_id)


async def clear_prompts(
    update: Update, context: ContextTypes.DEFAULT_TYPE, keep: int | None = None
) -> None:
    """Delete this flow's prompts, except `keep` -- the one holding the result.

    Deletion is best effort: a message may already be gone, be too old, or not
    be the bot's to remove, and none of that is worth failing the flow over.
    """
    chat_id = update.effective_chat.id

    for message_id in context.user_data.get("prompt_ids", []):
        if message_id == keep:
            continue
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except TelegramError:
            pass

    context.user_data["prompt_ids"] = []
