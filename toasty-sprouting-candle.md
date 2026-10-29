# Plan: `/manage_expenses` — Edit and Delete Expenses

## Context

The bot can log expenses but has no way to correct mistakes. This adds a `/manage_expenses` command that lets the user pick a recent expense and edit its amount, description, or date, or delete it entirely. The user stays in the conversation after each edit so they can make multiple changes in one session.

---

## Files to Change

| File                         | Action                         |
| ---------------------------- | ------------------------------ |
| `handlers/manage_expense.py` | Create new ConversationHandler |
| `repo/expense.py`            | Add 4 new repo functions       |
| `main.py`                    | Import + register handler      |

Reference files (read-only): `handlers/expense.py` (amount parsing pattern), `models/models.py` (field names)

---

## Step 1 — Repo Functions (`repo/expense.py`)

Add after the existing `add_expense`:

```
get_recent_expenses(chat_id: int, limit: int = 10) -> list[Row]
```

- `select(Expense, Category.name).join(Category, Expense.category_id == Category.id)`
- Filter `Expense.chat_id == chat_id`
- Order by `spent_at DESC`, `created_at DESC`; `.limit(limit)`
- Access via `row.Expense` and `row.name`

```
get_expense_by_id(expense_id: int, chat_id: int) -> Row | None
```

- Same join; filter `Expense.id == expense_id` AND `Expense.chat_id == chat_id` (ownership check)

```
update_expense(expense_id: int, **kwargs) -> bool
```

- Fetch by id, `setattr` for each kwarg (`amount`, `description`, `spent_at`), commit
- Return `False` if not found

```
delete_expense(expense_id: int, chat_id: int) -> bool
```

- Fetch with ownership check, `session.delete()`, commit; return `False` if not found

---

## Step 2 — Handler (`handlers/manage_expense.py`)

### State constants (start at 10 to avoid collision with expense.py's 1–5)

```
LISTING=10, OPTIONS=11, EDIT_AMOUNT=12, EDIT_DESC=13, EDIT_DATE=14, CONFIRM_DELETE=15
```

### Callback data (all prefixed `mexp_`)

```
mexp_cancel, mexp_sel_{id}, mexp_edit_amount, mexp_edit_desc, mexp_edit_date,
mexp_delete, mexp_clear_desc, mexp_today, mexp_confirm_del, mexp_abort_del
```

### Functions

**`manage_expenses(update, context)`** — entry  
Calls `get_recent_expenses(chat_id)`. If empty → "No expenses found." + END.  
One button per expense, label: `$25.50 | Category | 2024-01-15`, `callback_data=mexp_sel_{id}`.  
Plus Cancel button. Returns `LISTING`.

**`expense_selected(update, context)`** — LISTING, pattern `r"^mexp_sel_\d+$"`  
Parse `expense_id` from callback data. Store in `context.user_data["mexp_expense_id"]`.  
Call `get_expense_by_id`. If None → "Expense not found." + END.  
Store data needed for display; call `_show_options(update, context)`; return `OPTIONS`.

**`_show_options(update, context)`** — internal helper  
Fetches fresh expense data and displays current values + keyboard:

- Row 1: `[Edit Amount | Edit Description]`
- Row 2: `[Edit Date | Delete]`
- Row 3: `[Cancel]`
  Branches on `update.callback_query is not None` to use `edit_message_text` vs `reply_text`.

**Edit amount flow** — OPTIONS → EDIT_AMOUNT  
`choose_edit_amount`: edits message to "Enter new amount (e.g. 12+3):"; returns `EDIT_AMOUNT`.  
`edit_amount_received`: same parsing as `expense.py::amount_received` (split `+`, replace `,` with `.`, sum floats, reject ≤ 0). On success: `update_expense(id, amount=...)`, re-show options, return `OPTIONS`.

**Edit description flow** — OPTIONS → EDIT_DESC  
`choose_edit_desc`: message + `[Clear]` button + `[Cancel]`; returns `EDIT_DESC`.  
`edit_desc_received`: `update_expense(id, description=text.strip())`; re-show options; return `OPTIONS`.  
`clear_desc` (pattern `mexp_clear_desc`): `update_expense(id, description=None)`; re-show options; return `OPTIONS`.

**Edit date flow** — OPTIONS → EDIT_DATE  
`choose_edit_date`: message + `[Today]` button + `[Cancel]`; returns `EDIT_DATE`.  
`edit_date_today` (pattern `mexp_today`): `update_expense(id, spent_at=date.today())`; re-show options; return `OPTIONS`.  
`edit_date_received`: `date.fromisoformat(text.strip())`, re-prompt on `ValueError`; on success update + re-show; return `OPTIONS`.

**Delete flow** — OPTIONS → CONFIRM_DELETE  
`choose_delete`: "Are you sure? This cannot be undone." + `[Yes, Delete]` / `[No, Go Back]`; return `CONFIRM_DELETE`.  
`confirm_delete` (pattern `mexp_confirm_del`): `delete_expense(id, chat_id)`, clear `user_data`, "Expense deleted.", return END.  
`abort_delete` (pattern `mexp_abort_del`): re-show options, return `OPTIONS`.

**`cancel(update, context)`** — available in all states  
Answer callback if present, edit/reply "Cancelled.", clear `user_data`, return END.

### ConversationHandler

```python
manage_expense_handler = ConversationHandler(
    entry_points=[CommandHandler("manage_expenses", manage_expenses)],
    states={
        LISTING:        [CallbackQueryHandler(expense_selected, r"^mexp_sel_\d+$"),
                         CallbackQueryHandler(cancel, r"^mexp_cancel$")],
        OPTIONS:        [CallbackQueryHandler(choose_edit_amount, r"^mexp_edit_amount$"),
                         CallbackQueryHandler(choose_edit_desc,   r"^mexp_edit_desc$"),
                         CallbackQueryHandler(choose_edit_date,   r"^mexp_edit_date$"),
                         CallbackQueryHandler(choose_delete,      r"^mexp_delete$"),
                         CallbackQueryHandler(cancel,             r"^mexp_cancel$")],
        EDIT_AMOUNT:    [MessageHandler(TEXT & ~COMMAND, edit_amount_received),
                         CallbackQueryHandler(cancel, r"^mexp_cancel$")],
        EDIT_DESC:      [MessageHandler(TEXT & ~COMMAND, edit_desc_received),
                         CallbackQueryHandler(clear_desc, r"^mexp_clear_desc$"),
                         CallbackQueryHandler(cancel,     r"^mexp_cancel$")],
        EDIT_DATE:      [CallbackQueryHandler(edit_date_today, r"^mexp_today$"),
                         MessageHandler(TEXT & ~COMMAND, edit_date_received),
                         CallbackQueryHandler(cancel, r"^mexp_cancel$")],
        CONFIRM_DELETE: [CallbackQueryHandler(confirm_delete, r"^mexp_confirm_del$"),
                         CallbackQueryHandler(abort_delete,   r"^mexp_abort_del$"),
                         CallbackQueryHandler(cancel,         r"^mexp_cancel$")],
    },
    fallbacks=[CallbackQueryHandler(cancel, r"^mexp_cancel$")],
)
```

---

## Step 3 — Register in `main.py`

```python
from handlers.manage_expense import manage_expense_handler
# ...
application.add_handler(manage_expense_handler)  # after add_expense_handler
```

---

## Key Pitfalls

- **`_show_options` after MessageHandler**: text message flows (EDIT_AMOUNT/DESC/DATE) have no `callback_query` to edit — must use `reply_text`, not `edit_message_text`. Branch on `update.callback_query is not None`.
- **Amount parsing**: duplicate the ~6-line parsing logic from `handlers/expense.py` directly in `manage_expense.py` to avoid circular imports (no shared utils file exists).
- **SQLAlchemy Row access**: `row.Expense` for the model instance, `row.name` for the joined column — not index access.
- **`update_expense(description=None)`**: `setattr` with `None` → SQL NULL. No special casing needed.
- **State numbers**: keep LISTING–CONFIRM_DELETE at 10–15, separate from expense.py's 1–5.

---

## Verification

1. Run `python main.py`
2. `/manage_expenses` with no expenses → "No expenses found."
3. After adding an expense: list appears with correct label format
4. Tap expense → options keyboard appears with current values
5. Edit amount with expression `"12 + 3"` → updates to 15.00, options reappear
6. Edit description → updates; "Clear" → sets to null
7. Edit date with invalid string → re-prompts; "Today" → sets today's date
8. Delete → confirmation prompt; "No" → back to options; "Yes" → deleted, conversation ends
9. Cancel at any step → "Cancelled.", conversation ends
