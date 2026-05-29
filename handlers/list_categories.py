from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from repo.category import get_top_level_categories, get_subcategories


async def list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    top_level = get_top_level_categories(chat_id)

    if not top_level:
        await update.message.reply_text("You have no categories yet. Use /add_category to create one.")
        return

    lines = ["<b>Categories</b>", "------------"]

    for category in top_level:
        lines.append(f"\n<b>{category.name}</b>")
        subcategories = get_subcategories(category.id, chat_id)
        for sub in subcategories:
            lines.append(f"- {sub.name}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


list_categories_handler = CommandHandler("list_categories", list_categories)
