import html
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from handlers.pickers import category_markup, chosen_id
from handlers.prompts import clear_prompts, track_prompt
from handlers.rich import edit_rich, send_rich
from handlers.summary import expense_blocks
from repo.category import get_subcategories, get_top_level_categories
from repo.expense import (
    count_for_chat,
    delete_expense,
    get_owned,
    get_page,
    set_amount,
    set_category,
    set_description,
    set_spent_at,
)
from utils import clock, currency
from utils.amounts import parse_amount

# Enough rows to cover a few days of spending without the keyboard needing a
# scroll of its own.
PER_PAGE = 6

# Callbacks
EXPENSE_PREFIX = "mex_exp"
OPEN_PREFIX = "mex_open"
CATEGORY_PREFIX = "mex_cat"

OLDER = "mex_older"
NEWER = "mex_newer"
AMOUNT = "mex_amount"
CATEGORY = "mex_category"
DESCRIPTION = "mex_description"
DATE = "mex_date"
DELETE = "mex_delete"
CLEAR = "mex_clear"
TODAY = "mex_today"
CONFIRM = "mex_confirm"
USE_PARENT = "mex_parent"
LIST = "mex_list"
CLOSE = "mex_close"
BACK = "mex_back"
CANCEL = "mex_cancel"

CANCEL_BUTTON = InlineKeyboardButton("Cancel", callback_data=CANCEL)
BACK_BUTTON = InlineKeyboardButton("Back", callback_data=BACK)
BACK_MARKUP = InlineKeyboardMarkup([[BACK_BUTTON]])

# Not "Cancel": every field is written the moment it is sent, so by the time
# this keyboard is on screen there is nothing left to call off.
CARD_MARKUP = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("Amount", callback_data=AMOUNT),
            InlineKeyboardButton("Category", callback_data=CATEGORY),
        ],
        [
            InlineKeyboardButton("Description", callback_data=DESCRIPTION),
            InlineKeyboardButton("Date", callback_data=DATE),
        ],
        [InlineKeyboardButton("Delete", callback_data=DELETE)],
        [
            InlineKeyboardButton("List", callback_data=LIST),
            InlineKeyboardButton("Close", callback_data=CLOSE),
        ],
    ]
)

GONE = "That expense no longer exists."
UNDONE = "This cannot be undone."

# The heading a card carries when it is simply being looked at; an edit
# replaces it with what the edit did.
CARD_TITLE = "Expense"


def edit_markup(expense_id: int) -> InlineKeyboardMarkup:
    """The button that reopens one expense for editing.

    Defined here rather than where it gets attached, because the callback data
    it carries is this conversation's entry point and the two have to agree on
    it. Everything needed to find the row rides in the button, so one of these
    still works long after the flow that sent it ended.
    """
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Edit", callback_data=f"{OPEN_PREFIX}_{expense_id}")]]
    )

# How much of a description a button can carry before the label stops being
# readable. Telegram elides what overflows, which loses the date and amount
# at the far end rather than the tail of a long note.
LABEL_DETAIL = 30

# States
BROWSING = 1
VIEWING = 2
TYPING_AMOUNT = 3
CHOOSING_CATEGORY = 4
CHOOSING_SUBCATEGORY = 5
TYPING_DESCRIPTION = 6
CHOOSING_DATE = 7
CONFIRMING_DELETE = 8


def short_date(value: date) -> str:
    """A date as it reads in a list, without a padding zero on the day."""
    return f"{value.day} {value:%b}"


def money(expense) -> str:
    """An expense's amount in the currency it was recorded in, not today's."""
    return currency.format_amount(expense.amount, expense.currency)


def row_label(expense) -> str:
    """One expense as a button.

    Button text is not parsed as HTML, so nothing here is escaped: a category
    called "Food & Drink" has to reach the user with its ampersand intact.
    """
    detail = expense.description or expense.category_name

    if len(detail) > LABEL_DETAIL:
        detail = f"{detail[: LABEL_DETAIL - 1].rstrip()}..."

    return f"{short_date(expense.spent_at)} · {money(expense)} · {detail}"


async def show(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, markup) -> None:
    """Put a screen in front of the user, wherever the flow arrived from.

    A button press edits the message it came from, so the flow stays in one
    place in the chat however many screens it moves through. A typed message
    cannot be answered that way -- the screen would sit above what the user
    just sent -- so a fresh one is posted and the previous one tidied away,
    which keeps the flow at the bottom of the chat where the user is looking.
    """
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=markup, parse_mode="HTML"
        )
        return

    prompt = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=markup,
        parse_mode="HTML",
    )
    await clear_prompts(update, context)
    track_prompt(context, prompt)


async def show_rich(update: Update, context: ContextTypes.DEFAULT_TYPE, blocks, markup) -> None:
    """Put a rich screen in front of the user, the way `show` does a plain one.

    Same rule: a button press edits the message it came from, so the flow stays
    in one place in the chat, while a typed message gets a fresh screen at the
    bottom and the previous one tidied away.
    """
    chat_id = update.effective_chat.id

    if update.callback_query:
        await edit_rich(
            context, chat_id, update.callback_query.message.message_id, blocks, markup
        )
        return

    prompt = await send_rich(context, chat_id, blocks, markup)
    await clear_prompts(update, context)
    track_prompt(context, prompt)


async def finish_with(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Close the flow on the message the user is looking at, saying why."""
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML")
        keep = update.callback_query.message.message_id
    else:
        final = await update.message.reply_text(text, parse_mode="HTML")
        keep = final.message_id

    await clear_prompts(update, context, keep=keep)
    context.user_data.clear()
    return ConversationHandler.END


async def render_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE, status: str | None = None
):
    """Draw a page of expenses, newest first.

    The page is read back from the database on every pass rather than cached,
    so a row edited or deleted during the flow is gone from the list the next
    time the list is drawn. The page number is clamped to what now exists,
    because deleting the last row on the last page leaves the user standing
    past the end of the list.
    """
    chat_id = update.effective_chat.id
    total = count_for_chat(chat_id)

    if total == 0:
        return await finish_with(
            update, context, "You have not logged any expenses yet. Use /add_expense to add one."
        )

    pages = (total + PER_PAGE - 1) // PER_PAGE
    page = min(context.user_data.get("page", 1), pages)
    expenses = get_page(chat_id, (page - 1) * PER_PAGE, PER_PAGE)

    if not expenses:
        page = 1
        expenses = get_page(chat_id, 0, PER_PAGE)

    context.user_data["page"] = page

    newest = short_date(expenses[0].spent_at)
    oldest = short_date(expenses[-1].spent_at)
    span = newest if newest == oldest else f"{oldest} - {newest}"

    lines = [f"<b>Expenses</b> · {span}", f"page {page} of {pages}"]

    if status:
        lines = [f"<i>{html.escape(status)}</i>", ""] + lines

    rows = [
        [InlineKeyboardButton(row_label(expense), callback_data=f"{EXPENSE_PREFIX}_{expense.id}")]
        for expense in expenses
    ]

    navigation = []
    if page < pages:
        navigation.append(InlineKeyboardButton("Older", callback_data=OLDER))
    if page > 1:
        navigation.append(InlineKeyboardButton("Newer", callback_data=NEWER))
    if navigation:
        rows.append(navigation)

    rows.append([CANCEL_BUTTON])

    await show(update, context, "\n".join(lines), InlineKeyboardMarkup(rows))
    return BROWSING


def card_blocks(expense, title: str = CARD_TITLE) -> list[dict]:
    """One expense in full, in the layout it is shown in anywhere.

    The title doubles as the report of what just happened, so an edit needs
    no line of its own above the detail it is an edit to.
    """
    return expense_blocks(
        title=title,
        category=expense.category_path,
        description=expense.description,
        amount=expense.amount,
        code=expense.currency,
        spent_at=expense.spent_at,
    )


async def render_card(
    update: Update, context: ContextTypes.DEFAULT_TYPE, title: str = CARD_TITLE
):
    """Draw the card for the expense being edited, re-reading it first.

    Every edit comes back through here instead of patching the text it was
    launched from, so the card always shows what the database holds -- and a
    row that went away in the meantime is reported rather than drawn.
    """
    expense = get_owned(context.user_data["expense_id"], update.effective_chat.id)

    if expense is None:
        return await finish_with(update, context, GONE)

    await show_rich(update, context, card_blocks(expense, title), CARD_MARKUP)
    return VIEWING


async def manage_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["page"] = 1
    return await render_list(update, context)


async def open_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open one expense's card straight from a button that named it.

    The id travels in the callback data, so the Edit button on a confirmation
    works whenever it is tapped -- a week later, or after a restart that
    forgot every conversation -- since finding the row needs nothing the
    button does not carry. The card is posted as a new message: the
    confirmation it was tapped on is the record of the expense being added,
    and overwriting that would lose it.
    """
    expense = get_owned(chosen_id(update), update.effective_chat.id)

    # The row is looked up before the query is answered, because a query takes
    # one answer: saying it is gone has to be that answer, not a second one.
    if expense is None:
        await update.callback_query.answer(GONE, show_alert=True)
        return ConversationHandler.END

    await update.callback_query.answer()

    context.user_data["expense_id"] = expense.id
    context.user_data["page"] = 1

    prompt = await send_rich(
        context, update.effective_chat.id, card_blocks(expense), CARD_MARKUP
    )
    track_prompt(context, prompt)
    return VIEWING


async def expense_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    context.user_data["expense_id"] = chosen_id(update)
    return await render_card(update, context)


async def older(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    context.user_data["page"] = context.user_data.get("page", 1) + 1
    return await render_list(update, context)


async def newer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    context.user_data["page"] = max(1, context.user_data.get("page", 1) - 1)
    return await render_list(update, context)


async def back_to_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await render_list(update, context)


async def back_to_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await render_card(update, context)


async def edit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    expense = get_owned(context.user_data["expense_id"], update.effective_chat.id)

    if expense is None:
        return await finish_with(update, context, GONE)

    await show(
        update,
        context,
        f"Currently {html.escape(money(expense))}.\nSend the new amount:",
        BACK_MARKUP,
    )
    return TYPING_AMOUNT


async def amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount = parse_amount(update.message.text)

    if amount is None:
        prompt = await update.message.reply_text(
            "Please enter a valid positive number (e.g. 12.50):",
            reply_markup=BACK_MARKUP,
        )
        track_prompt(context, prompt)
        return TYPING_AMOUNT

    expense = set_amount(context.user_data["expense_id"], update.effective_chat.id, amount)

    if expense is None:
        return await finish_with(update, context, GONE)

    return await render_card(update, context, title="Amount Updated")


async def edit_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    chat_id = update.effective_chat.id
    categories = get_top_level_categories(chat_id)

    if not categories:
        return await finish_with(
            update, context, "You have no categories. Use /add_category to create one first."
        )

    context.user_data["category_names"] = {cat.id: cat.name for cat in categories}

    await show(
        update,
        context,
        "Choose a category:",
        category_markup(categories, CATEGORY_PREFIX, [BACK_BUTTON]),
    )
    return CHOOSING_CATEGORY


async def category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    category_id = chosen_id(update)
    chat_id = update.effective_chat.id
    subcategories = get_subcategories(category_id, chat_id)

    if not subcategories:
        return await apply_category(update, context, category_id)

    context.user_data["category_names"].update({cat.id: cat.name for cat in subcategories})
    context.user_data["parent_category_id"] = category_id

    parent_name = context.user_data["category_names"][category_id]
    use_parent = [
        InlineKeyboardButton(f"Use '{parent_name}' directly", callback_data=USE_PARENT)
    ]

    await show(
        update,
        context,
        "Choose a subcategory:",
        category_markup(subcategories, CATEGORY_PREFIX, [BACK_BUTTON], extra_row=use_parent),
    )
    return CHOOSING_SUBCATEGORY


async def subcategory_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await apply_category(update, context, chosen_id(update))


async def parent_category_used(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await apply_category(update, context, context.user_data["parent_category_id"])


async def back_to_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await edit_category(update, context)


async def apply_category(
    update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: int
):
    """Move the expense, then show what it now reads as.

    A miss covers either side going away, since both the expense and the
    category were named by a button and either could have been deleted since
    it was drawn.
    """
    expense = set_category(
        context.user_data["expense_id"], update.effective_chat.id, category_id
    )

    if expense is None:
        return await finish_with(update, context, "That expense or category no longer exists.")

    return await render_card(update, context, title="Category Updated")


async def edit_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    expense = get_owned(context.user_data["expense_id"], update.effective_chat.id)

    if expense is None:
        return await finish_with(update, context, GONE)

    if expense.description:
        text = f"Currently '{html.escape(expense.description)}'.\nSend a new description:"
        keyboard = [[InlineKeyboardButton("Clear", callback_data=CLEAR)], [BACK_BUTTON]]
    else:
        text = "This expense has no description.\nSend one:"
        keyboard = [[BACK_BUTTON]]

    await show(update, context, text, InlineKeyboardMarkup(keyboard))
    return TYPING_DESCRIPTION


async def description_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = update.message.text.strip()

    if not description:
        prompt = await update.message.reply_text(
            "Send a description, or use Clear to remove the one that is there:",
            reply_markup=BACK_MARKUP,
        )
        track_prompt(context, prompt)
        return TYPING_DESCRIPTION

    expense = set_description(
        context.user_data["expense_id"], update.effective_chat.id, description
    )

    if expense is None:
        return await finish_with(update, context, GONE)

    return await render_card(update, context, title="Description Updated")


async def description_cleared(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    expense = set_description(context.user_data["expense_id"], update.effective_chat.id, None)

    if expense is None:
        return await finish_with(update, context, GONE)

    return await render_card(update, context, title="Description Cleared")


async def edit_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    expense = get_owned(context.user_data["expense_id"], update.effective_chat.id)

    if expense is None:
        return await finish_with(update, context, GONE)

    keyboard = [[InlineKeyboardButton("Today", callback_data=TODAY)], [BACK_BUTTON]]

    await show(
        update,
        context,
        f"Spent on {expense.spent_at}.\n"
        "Send a date (YYYY-MM-DD) or tap Today:",
        InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_DATE


async def date_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        spent_at = date.fromisoformat(update.message.text.strip())
    except ValueError:
        prompt = await update.message.reply_text(
            "Invalid date format. Please use YYYY-MM-DD (e.g. 2024-05-20):",
            reply_markup=BACK_MARKUP,
        )
        track_prompt(context, prompt)
        return CHOOSING_DATE

    return await apply_date(update, context, spent_at)


async def date_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await apply_date(update, context, clock.today())


async def apply_date(update: Update, context: ContextTypes.DEFAULT_TYPE, spent_at: date):
    expense = set_spent_at(context.user_data["expense_id"], update.effective_chat.id, spent_at)

    if expense is None:
        return await finish_with(update, context, GONE)

    return await render_card(update, context, title="Date Updated")


async def ask_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Spell out which expense is going before anything is written, since none of it undoes."""
    await update.callback_query.answer()

    expense = get_owned(context.user_data["expense_id"], update.effective_chat.id)

    if expense is None:
        return await finish_with(update, context, GONE)

    blocks = card_blocks(expense, title="Delete This Expense?") + [
        {"type": "paragraph", "text": UNDONE}
    ]

    keyboard = [[InlineKeyboardButton("Delete", callback_data=CONFIRM)], [BACK_BUTTON]]

    await show_rich(update, context, blocks, InlineKeyboardMarkup(keyboard))
    return CONFIRMING_DELETE


async def delete_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete, then go back to the list, where the row is now missing."""
    await update.callback_query.answer()

    expense = delete_expense(context.user_data["expense_id"], update.effective_chat.id)

    if expense is None:
        return await finish_with(update, context, GONE)

    context.user_data.pop("expense_id", None)

    return await render_list(
        update,
        context,
        status=f"Deleted {money(expense)} · {expense.category_path}.",
    )


async def close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finish, leaving the card as the record of what the expense now is.

    The keyboard comes off as it goes. Every field was written the moment it
    was sent, so there is nothing here to save or confirm and the only thing
    closing has to do is visible: buttons that outlive the conversation they
    belong to answer nothing when they are pressed, and a button that does
    nothing is one the user presses again.
    """
    await update.callback_query.answer()
    await update.callback_query.edit_message_reply_markup(reply_markup=None)

    await clear_prompts(update, context, keep=update.callback_query.message.message_id)
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Expense management cancelled."

    if update.callback_query:
        await update.callback_query.answer()
        return await finish_with(update, context, text)

    await update.message.reply_text(text)
    await clear_prompts(update, context)
    context.user_data.clear()
    return ConversationHandler.END


manage_expenses_handler = ConversationHandler(
    entry_points=[
        CommandHandler("manage_expenses", manage_expenses),
        CallbackQueryHandler(open_expense, pattern=rf"^{OPEN_PREFIX}_\d+$"),
    ],
    states={
        BROWSING: [
            CallbackQueryHandler(expense_chosen, pattern=rf"^{EXPENSE_PREFIX}_\d+$"),
            CallbackQueryHandler(older, pattern=f"^{OLDER}$"),
            CallbackQueryHandler(newer, pattern=f"^{NEWER}$"),
            CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        ],
        VIEWING: [
            CallbackQueryHandler(edit_amount, pattern=f"^{AMOUNT}$"),
            CallbackQueryHandler(edit_category, pattern=f"^{CATEGORY}$"),
            CallbackQueryHandler(edit_description, pattern=f"^{DESCRIPTION}$"),
            CallbackQueryHandler(edit_date, pattern=f"^{DATE}$"),
            CallbackQueryHandler(ask_delete, pattern=f"^{DELETE}$"),
            CallbackQueryHandler(back_to_list, pattern=f"^{LIST}$"),
            CallbackQueryHandler(close, pattern=f"^{CLOSE}$"),
        ],
        TYPING_AMOUNT: [
            CallbackQueryHandler(back_to_card, pattern=f"^{BACK}$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, amount_received),
        ],
        CHOOSING_CATEGORY: [
            CallbackQueryHandler(category_chosen, pattern=rf"^{CATEGORY_PREFIX}_\d+$"),
            CallbackQueryHandler(back_to_card, pattern=f"^{BACK}$"),
        ],
        CHOOSING_SUBCATEGORY: [
            CallbackQueryHandler(subcategory_chosen, pattern=rf"^{CATEGORY_PREFIX}_\d+$"),
            CallbackQueryHandler(parent_category_used, pattern=f"^{USE_PARENT}$"),
            CallbackQueryHandler(back_to_categories, pattern=f"^{BACK}$"),
        ],
        TYPING_DESCRIPTION: [
            CallbackQueryHandler(description_cleared, pattern=f"^{CLEAR}$"),
            CallbackQueryHandler(back_to_card, pattern=f"^{BACK}$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, description_received),
        ],
        CHOOSING_DATE: [
            CallbackQueryHandler(date_today, pattern=f"^{TODAY}$"),
            CallbackQueryHandler(back_to_card, pattern=f"^{BACK}$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, date_received),
        ],
        CONFIRMING_DELETE: [
            CallbackQueryHandler(delete_confirmed, pattern=f"^{CONFIRM}$"),
            CallbackQueryHandler(back_to_card, pattern=f"^{BACK}$"),
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
    ],
    # So an Edit button still opens its expense while another one is already
    # open. Entry points are tried before the current state's handlers, and
    # neither of them collides with a button this flow draws, so the only
    # thing reentry changes is that those two always work.
    allow_reentry=True,
)
