from datetime import date
from decimal import Decimal

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
