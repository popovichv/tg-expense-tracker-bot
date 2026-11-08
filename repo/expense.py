from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import aliased

from database import SessionLocal
from models.models import Category, Expense

# A subcategory's parent, for the breadcrumb an expense is shown with. Aliased
# because the join reaches Category twice: once for the expense's own category,
# and once for whatever that one hangs under.
ParentCategory = aliased(Category)


@dataclass
class ExpenseView:
    """One expense as it is read for display, with its category named.

    A dataclass rather than the ORM row, for two reasons: the row goes
    detached the moment its session closes, and the category name lives on
    another table, so a caller holding an `Expense` cannot render one without
    going back to the database.

    `parent_name` is set only when the category is a subcategory.
    """

    id: int
    amount: Decimal
    description: str | None
    spent_at: date
    category_id: int
    category_name: str
    parent_name: str | None

    @property
    def category_path(self) -> str:
        """The category as it reads to the user, parent included."""
        if self.parent_name is None:
            return self.category_name

        return f"{self.parent_name} > {self.category_name}"


# Positional, and in the order ExpenseView takes them, so a row built by
# view_query can be unpacked straight into one.
VIEW_COLUMNS = (
    Expense.id,
    Expense.amount,
    Expense.description,
    Expense.spent_at,
    Expense.category_id,
    Category.name,
    ParentCategory.name,
)


def owned(expense_id: int, chat_id: int):
    """A query for one expense that will only ever match its owner's row.

    Expense ids reach the repo from inline keyboard callback data, so they are
    matched together with the chat rather than trusted: a stale or forged
    button finds nothing instead of someone else's expense.
    """
    return select(Expense).where(
        Expense.id == expense_id,
        Expense.chat_id == chat_id,
    )


def view_query(chat_id: int):
    """The display columns for one chat's expenses, joined to their categories."""
    return (
        select(*VIEW_COLUMNS)
        .join(Category, Category.id == Expense.category_id)
        .outerjoin(ParentCategory, ParentCategory.id == Category.parent_id)
        .where(Expense.chat_id == chat_id)
    )


def read_view(session, expense_id: int, chat_id: int) -> ExpenseView | None:
    """Read one expense for display inside a caller's transaction."""
    row = session.execute(view_query(chat_id).where(Expense.id == expense_id)).first()

    return ExpenseView(*row) if row is not None else None


def add_expense(
    chat_id: int,
    category_id: int,
    amount: Decimal,
    description: str | None,
    spent_at: date,
) -> Expense:
    with SessionLocal() as session:
        expense = Expense(
            chat_id=chat_id,
            category_id=category_id,
            amount=amount,
            description=description,
            spent_at=spent_at,
        )
        session.add(expense)
        session.commit()
        session.refresh(expense)
        return expense


def count_for_chat(chat_id: int) -> int:
    """How many expenses this chat has logged, for paging the list."""
    with SessionLocal() as session:
        result = session.execute(
            select(func.count()).select_from(Expense).where(Expense.chat_id == chat_id)
        )
        return result.scalar_one()


def get_page(chat_id: int, offset: int, limit: int) -> list[ExpenseView]:
    """One page of expenses, newest first.

    Ordered by id as well as date because `spent_at` is a date, not a moment:
    several expenses share one, and without a tiebreak the database is free to
    return them in a different order each time, which would shuffle rows
    between pages as the user walks through them.
    """
    with SessionLocal() as session:
        rows = session.execute(
            view_query(chat_id)
            .order_by(Expense.spent_at.desc(), Expense.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return [ExpenseView(*row) for row in rows]


def get_owned(expense_id: int, chat_id: int) -> ExpenseView | None:
    """One expense for display, or None if it is not this chat's."""
    with SessionLocal() as session:
        return read_view(session, expense_id, chat_id)


def _update(expense_id: int, chat_id: int, **values) -> ExpenseView | None:
    """Write new values onto one expense and return how it now reads.

    None means this chat has no such expense. Callers treat that as an answer
    rather than a failure: a button outlives the row it points at, so "it is
    gone" is something the flow has to be able to say.
    """
    with SessionLocal() as session:
        expense = session.execute(owned(expense_id, chat_id)).scalars().first()

        if expense is None:
            return None

        for field, value in values.items():
            setattr(expense, field, value)

        session.commit()
        return read_view(session, expense_id, chat_id)


def set_amount(expense_id: int, chat_id: int, amount: Decimal) -> ExpenseView | None:
    """Correct an amount."""
    return _update(expense_id, chat_id, amount=amount)


def set_description(expense_id: int, chat_id: int, description: str | None) -> ExpenseView | None:
    """Rewrite a description, or clear it with None."""
    return _update(expense_id, chat_id, description=description)


def set_spent_at(expense_id: int, chat_id: int, spent_at: date) -> ExpenseView | None:
    return _update(expense_id, chat_id, spent_at=spent_at)


def set_category(expense_id: int, chat_id: int, category_id: int) -> ExpenseView | None:
    """Move an expense to another category, if both of them are this chat's.

    The destination arrives from a button too, so it is matched against the
    chat the way the expense is, rather than handed to the foreign key to find
    out. Both reads and the write share one transaction, so the category
    cannot go away between being checked and being pointed at.
    """
    with SessionLocal() as session:
        expense = session.execute(owned(expense_id, chat_id)).scalars().first()
        category = (
            session.execute(
                select(Category).where(
                    Category.id == category_id,
                    Category.chat_id == chat_id,
                )
            )
            .scalars()
            .first()
        )

        if expense is None or category is None:
            return None

        expense.category_id = category_id
        session.commit()
        return read_view(session, expense_id, chat_id)


def delete_expense(expense_id: int, chat_id: int) -> ExpenseView | None:
    """Delete one expense, returning what it was so the result can name it."""
    with SessionLocal() as session:
        expense = session.execute(owned(expense_id, chat_id)).scalars().first()

        if expense is None:
            return None

        view = read_view(session, expense_id, chat_id)
        session.delete(expense)
        session.commit()
        return view


@dataclass
class CategoryTotal:
    """What one category holds over a period.

    The category is named by id alone: the caller already needs the whole tree
    to place a subcategory under its parent, so it resolves names from there
    rather than having them repeated on every row.
    """

    category_id: int
    total: Decimal


def totals_by_category(chat_id: int, start: date, end: date) -> list[CategoryTotal]:
    """Spending per category between two dates, inclusive.

    A category with nothing in the period is absent rather than zero, which
    is what lets a report show only what was actually spent on.
    """
    with SessionLocal() as session:
        rows = session.execute(
            select(Expense.category_id, func.sum(Expense.amount))
            .where(
                Expense.chat_id == chat_id,
                Expense.spent_at >= start,
                Expense.spent_at <= end,
            )
            .group_by(Expense.category_id)
        )
        return [CategoryTotal(*row) for row in rows]


def earliest_spent_at(chat_id: int) -> date | None:
    """The date of this chat's oldest expense, or None if it has logged none.

    Bounds how far back a report can be scrolled, so walking backwards stops
    at the first month that has anything in it instead of going on forever.
    """
    with SessionLocal() as session:
        result = session.execute(
            select(func.min(Expense.spent_at)).where(Expense.chat_id == chat_id)
        )
        return result.scalar_one()


def count_in_session(session, category_ids: Sequence[int], chat_id: int) -> int:
    """How many expenses sit in these categories, read inside a caller's transaction."""
    if not category_ids:
        return 0

    result = session.execute(
        select(func.count())
        .select_from(Expense)
        .where(
            Expense.category_id.in_(category_ids),
            Expense.chat_id == chat_id,
        )
    )
    return result.scalar_one()


def count_for_categories(category_ids: Sequence[int], chat_id: int) -> int:
    """How many expenses sit in these categories, for anyone who just wants the number."""
    with SessionLocal() as session:
        return count_in_session(session, category_ids, chat_id)


def move_to_category(
    session, category_ids: Sequence[int], to_category_id: int, chat_id: int
) -> int:
    """Repoint expenses at a different category, returning how many moved.

    Takes the caller's session instead of opening one, because a move only makes
    sense committed together with whatever made it necessary: were the categories
    deleted in a separate transaction, a failure in between would leave expenses
    pointing at rows that are gone.
    """
    if not category_ids:
        return 0

    result = session.execute(
        update(Expense)
        .where(
            Expense.category_id.in_(category_ids),
            Expense.chat_id == chat_id,
        )
        .values(category_id=to_category_id)
    )
    return result.rowcount
