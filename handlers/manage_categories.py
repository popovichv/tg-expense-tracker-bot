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
from repo.category import (
    delete_category_branch,
    describe_deletion,
    find_duplicate,
    get_subcategories,
    get_top_level_categories,
    rename_category,
)

# Callbacks
RENAME = "mng_rename"
DELETE = "mng_delete"
PARENT = "mng_parent"
CONFIRM = "mng_confirm"
BACK = "mng_back"
CANCEL = "mng_cancel"

CATEGORY_PREFIX = "mng_cat"
DESTINATION_PREFIX = "mng_dest"

CANCEL_BUTTON = InlineKeyboardButton("Cancel", callback_data=CANCEL)
CANCEL_MARKUP = InlineKeyboardMarkup([[CANCEL_BUTTON]])
BACK_BUTTON = InlineKeyboardButton("Back", callback_data=BACK)

ACTION_PROMPT = "What do you want to do?"
ACTION_MARKUP = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("Rename a category", callback_data=RENAME)],
        [InlineKeyboardButton("Delete a category", callback_data=DELETE)],
        [CANCEL_BUTTON],
    ]
)

RENAME_ACTION = "rename"
DELETE_ACTION = "delete"

CATEGORY_PROMPTS = {
    RENAME_ACTION: "Choose a category to rename:",
    DELETE_ACTION: "Choose a category to delete:",
}

PARENT_LABELS = {
    RENAME_ACTION: "Rename '{name}' itself",
    DELETE_ACTION: "Delete '{name}' and everything in it",
}

# States
CHOOSING_ACTION = 1
CHOOSING_CATEGORY = 2
CHOOSING_SUBCATEGORY = 3
TYPING_NAME = 4
CHOOSING_DESTINATION = 5
CONFIRMING_DELETE = 6


def expense_count(count: int) -> str:
    return "1 expense" if count == 1 else f"{count} expenses"


def subcategory_count(count: int) -> str:
    return "1 subcategory" if count == 1 else f"{count} subcategories"


def category_rows(categories, prefix=CATEGORY_PREFIX):
    buttons = [
        InlineKeyboardButton(cat.name, callback_data=f"{prefix}_{cat.id}") for cat in categories
    ]
    return [buttons[i : i + 2] for i in range(0, len(buttons), 2)]


def category_markup(categories):
    return InlineKeyboardMarkup(category_rows(categories) + [[BACK_BUTTON, CANCEL_BUTTON]])


def destination_markup(categories):
    rows = category_rows(categories, prefix=DESTINATION_PREFIX)
    return InlineKeyboardMarkup(rows + [[BACK_BUTTON, CANCEL_BUTTON]])


def subcategory_markup(subcategories, parent_label):
    keyboard = category_rows(subcategories)
    keyboard.append([InlineKeyboardButton(parent_label, callback_data=PARENT)])
    keyboard.append([BACK_BUTTON, CANCEL_BUTTON])
    return InlineKeyboardMarkup(keyboard)


def chosen_id(update: Update) -> int:
    return int(update.callback_query.data.split("_")[2])


async def finish_with(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Close the flow on the message the user is looking at, saying why."""
    await update.callback_query.edit_message_text(text)
    await clear_prompts(update, context, keep=update.callback_query.message.message_id)
    context.user_data.clear()
    return ConversationHandler.END


async def manage_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = await update.message.reply_text(ACTION_PROMPT, reply_markup=ACTION_MARKUP)
    track_prompt(context, prompt)
    return CHOOSING_ACTION


async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Draw the top-level list, reached from the action menu or from Back.

    The empty case is checked here rather than at the command, because the
    action menu opens before we know which categories the action applies to.
    """
    chat_id = update.effective_chat.id
    categories = get_top_level_categories(chat_id)

    if not categories:
        return await finish_with(
            update, context, "You have no categories yet. Use /add_category to create one first."
        )

    context.user_data["category_names"] = {cat.id: cat.name for cat in categories}

    await update.callback_query.edit_message_text(
        CATEGORY_PROMPTS[context.user_data["action"]],
        reply_markup=category_markup(categories),
    )
    return CHOOSING_CATEGORY


async def rename_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    context.user_data["action"] = RENAME_ACTION
    return await show_categories(update, context)


async def delete_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    context.user_data["action"] = DELETE_ACTION
    return await show_categories(update, context)


async def back_to_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    await update.callback_query.edit_message_text(ACTION_PROMPT, reply_markup=ACTION_MARKUP)
    return CHOOSING_ACTION


async def back_to_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await show_categories(update, context)


async def leaf_chosen(
    update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: int, parent_id: int | None
):
    """Hand off to whichever action the user picked at the menu.

    Both pickers are shared, so this is the point the two actions diverge. The
    parent comes from the step the user arrived through rather than from a
    query: a top-level category has none whichever way it was picked.
    """
    if context.user_data["action"] == RENAME_ACTION:
        return await ask_for_name(update, context, category_id, parent_id)

    return await begin_delete(update, context, category_id, parent_id)


async def top_category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    category_id = chosen_id(update)
    chat_id = update.effective_chat.id
    subcategories = get_subcategories(category_id, chat_id)

    if not subcategories:
        return await leaf_chosen(update, context, category_id, parent_id=None)

    context.user_data["category_names"].update({cat.id: cat.name for cat in subcategories})
    context.user_data["parent_category_id"] = category_id

    label = PARENT_LABELS[context.user_data["action"]].format(
        name=context.user_data["category_names"][category_id]
    )

    await update.callback_query.edit_message_text(
        "Choose a subcategory:",
        reply_markup=subcategory_markup(subcategories, label),
    )
    return CHOOSING_SUBCATEGORY


async def subcategory_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    return await leaf_chosen(
        update, context, chosen_id(update), parent_id=context.user_data["parent_category_id"]
    )


async def parent_category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    return await leaf_chosen(
        update, context, context.user_data["parent_category_id"], parent_id=None
    )


async def ask_for_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: int, parent_id: int | None
):
    """Record which category is being renamed and ask for the new name.

    The parent is what scopes the duplicate check, so it is kept alongside.
    """
    name = context.user_data["category_names"][category_id]

    context.user_data["rename_id"] = category_id
    context.user_data["rename_parent_id"] = parent_id
    context.user_data["rename_name"] = name

    await update.callback_query.edit_message_text(
        f"Current name: '{name}'.\nSend the new name:",
        reply_markup=CANCEL_MARKUP,
    )
    return TYPING_NAME


async def received_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    chat_id = update.effective_chat.id
    category_id = context.user_data["rename_id"]
    parent_id = context.user_data["rename_parent_id"]
    old_name = context.user_data["rename_name"]

    if not name:
        prompt = await update.message.reply_text(
            "A category needs a name. Send one:",
            reply_markup=CANCEL_MARKUP,
        )
        track_prompt(context, prompt)
        return TYPING_NAME

    if name == old_name:
        prompt = await update.message.reply_text(
            f"'{old_name}' is already its name. Send a different one:",
            reply_markup=CANCEL_MARKUP,
        )
        track_prompt(context, prompt)
        return TYPING_NAME

    existing = find_duplicate(name, chat_id, parent_id, exclude_id=category_id)
    if existing is not None:
        where = "at the top level" if parent_id is None else "under that category"
        prompt = await update.message.reply_text(
            f"'{existing.name}' already exists {where}. Send a different name:",
            reply_markup=CANCEL_MARKUP,
        )
        track_prompt(context, prompt)
        return TYPING_NAME

    renamed = rename_category(category_id, chat_id, name)

    if renamed is None:
        await update.message.reply_text(f"'{old_name}' no longer exists.")
    else:
        await update.message.reply_text(f"Renamed '{old_name}' to '{renamed.name}'.")

    await clear_prompts(update, context)
    context.user_data.clear()
    return ConversationHandler.END


async def begin_delete(
    update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: int, parent_id: int | None
):
    """Work out what the delete would take with it, and what to ask about it.

    An empty category only needs confirming. A subcategory's expenses roll up
    to its parent already, so that is where they go without asking. A top-level
    category has no parent to absorb them, so the user picks where they land.
    """
    chat_id = update.effective_chat.id
    deletion = describe_deletion(category_id, chat_id)

    if deletion is None:
        return await finish_with(update, context, "That category no longer exists.")

    context.user_data["delete_id"] = category_id
    context.user_data["delete_name"] = deletion.name
    context.user_data["delete_subcategories"] = deletion.subcategory_names
    context.user_data["delete_expenses"] = deletion.expense_count

    if deletion.expense_count == 0:
        context.user_data["delete_move_to"] = None
        return await confirm_delete(update, context)

    if parent_id is not None:
        context.user_data["delete_move_to"] = parent_id
        return await confirm_delete(update, context)

    destinations = [cat for cat in get_top_level_categories(chat_id) if cat.id != category_id]

    if not destinations:
        return await finish_with(
            update,
            context,
            f"'{deletion.name}' holds {expense_count(deletion.expense_count)} and is your "
            "only category, so there is nowhere to move them. Add another category first.",
        )

    context.user_data["category_names"].update({cat.id: cat.name for cat in destinations})

    await update.callback_query.edit_message_text(
        f"{branch_holds(context, deletion.expense_count)}.\nWhere should they go?",
        reply_markup=destination_markup(destinations),
    )
    return CHOOSING_DESTINATION


def branch_holds(context: ContextTypes.DEFAULT_TYPE, count: int) -> str:
    name = context.user_data["delete_name"]
    subcategories = context.user_data["delete_subcategories"]

    if not subcategories:
        return f"'{name}' holds {expense_count(count)}"

    return (
        f"'{name}' and its {subcategory_count(len(subcategories))} "
        f"hold {expense_count(count)}"
    )


async def destination_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    context.user_data["delete_move_to"] = chosen_id(update)
    return await confirm_delete(update, context)


async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Spell out the consequence before anything is written, since none of it undoes."""
    data = context.user_data
    subcategories = data["delete_subcategories"]
    count = data["delete_expenses"]

    lines = [f"Delete '{data['delete_name']}'?"]

    if subcategories:
        lines.append(
            f"Its {subcategory_count(len(subcategories))} go too: {', '.join(subcategories)}."
        )

    if count:
        destination = data["category_names"][data["delete_move_to"]]
        lines.append(f"Its {expense_count(count)} will move to '{destination}'.")
    else:
        lines.append("No expenses are logged against it.")

    lines.append("This cannot be undone.")

    keyboard = [
        [InlineKeyboardButton("Delete", callback_data=CONFIRM)],
        [BACK_BUTTON, CANCEL_BUTTON],
    ]

    await update.callback_query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CONFIRMING_DELETE


async def delete_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    data = context.user_data
    move_to = data["delete_move_to"]
    deleted = delete_category_branch(data["delete_id"], update.effective_chat.id, move_to=move_to)

    if deleted is None:
        return await finish_with(update, context, f"'{data['delete_name']}' no longer exists.")

    text = f"Deleted '{deleted.name}'"

    if deleted.subcategory_names:
        text += f" and its {subcategory_count(len(deleted.subcategory_names))}"

    text += "."

    if deleted.expense_count:
        destination = data["category_names"][move_to]
        text += f" {expense_count(deleted.expense_count)} moved to '{destination}'."

    return await finish_with(update, context, text)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Category management cancelled."

    if update.callback_query:
        await update.callback_query.answer()
        return await finish_with(update, context, text)

    await update.message.reply_text(text)
    await clear_prompts(update, context)
    context.user_data.clear()
    return ConversationHandler.END


manage_categories_handler = ConversationHandler(
    entry_points=[CommandHandler("manage_categories", manage_categories)],
    states={
        CHOOSING_ACTION: [
            CallbackQueryHandler(rename_chosen, pattern=f"^{RENAME}$"),
            CallbackQueryHandler(delete_chosen, pattern=f"^{DELETE}$"),
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        ],
        CHOOSING_CATEGORY: [
            CallbackQueryHandler(top_category_chosen, pattern=rf"^{CATEGORY_PREFIX}_\d+$"),
            CallbackQueryHandler(back_to_action, pattern=f"^{BACK}$"),
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        ],
        CHOOSING_SUBCATEGORY: [
            CallbackQueryHandler(subcategory_chosen, pattern=rf"^{CATEGORY_PREFIX}_\d+$"),
            CallbackQueryHandler(parent_category_chosen, pattern=f"^{PARENT}$"),
            CallbackQueryHandler(back_to_categories, pattern=f"^{BACK}$"),
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        ],
        TYPING_NAME: [
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, received_name),
        ],
        CHOOSING_DESTINATION: [
            CallbackQueryHandler(destination_chosen, pattern=rf"^{DESTINATION_PREFIX}_\d+$"),
            CallbackQueryHandler(back_to_categories, pattern=f"^{BACK}$"),
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        ],
        CONFIRMING_DELETE: [
            CallbackQueryHandler(delete_confirmed, pattern=f"^{CONFIRM}$"),
            CallbackQueryHandler(back_to_categories, pattern=f"^{BACK}$"),
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
    ],
)
