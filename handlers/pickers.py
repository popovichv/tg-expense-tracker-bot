"""The category keyboard every flow picks a category with.

Four flows now draw the same grid, and the one thing they must agree on is
how an id travels in callback data: each flow owns a prefix so its buttons
cannot be answered by another flow's handler, and `chosen_id` reads the id
back without caring which prefix it was.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update


def category_rows(categories, prefix: str) -> list[list[InlineKeyboardButton]]:
    """The categories as buttons, two to a row."""
    buttons = [
        InlineKeyboardButton(category.name, callback_data=f"{prefix}_{category.id}")
        for category in categories
    ]
    return [buttons[i : i + 2] for i in range(0, len(buttons), 2)]


def category_markup(
    categories,
    prefix: str,
    footer: list[InlineKeyboardButton],
    extra_row: list[InlineKeyboardButton] | None = None,
) -> InlineKeyboardMarkup:
    """The grid, then anything the flow adds to it, then its navigation row.

    `extra_row` is where a choice that is not a category goes -- using a
    parent category directly, say -- which belongs with the grid rather than
    among the navigation buttons underneath.
    """
    rows = category_rows(categories, prefix)

    if extra_row:
        rows.append(extra_row)

    rows.append(footer)
    return InlineKeyboardMarkup(rows)


def chosen_id(update: Update) -> int:
    """The category id from the button that was tapped."""
    return int(update.callback_query.data.rsplit("_", 1)[1])
