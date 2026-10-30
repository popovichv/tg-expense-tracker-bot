from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select, update

from database import SessionLocal
from utils.currency import DEFAULT_CURRENCY
from models.models import Expense


def add_expense(
    chat_id: int,
    category_id: int,
    amount: Decimal,
    description: str | None,
    spent_at: date,
    currency: str = DEFAULT_CURRENCY,
) -> Expense:
    with SessionLocal() as session:
        expense = Expense(
            chat_id=chat_id,
            category_id=category_id,
            amount=amount,
            description=description,
            spent_at=spent_at,
            currency=currency,
        )
        session.add(expense)
        session.commit()
        session.refresh(expense)
        return expense


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
