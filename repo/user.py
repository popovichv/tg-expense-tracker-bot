from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from utils.currency import DEFAULT_CURRENCY
from models.models import User
from repo.category import build_default_categories


def get_or_create_user(chat_id: int, name: str) -> tuple[User, bool]:
    """Return the user for this chat, creating the row only if it is missing.

    A new user is given their own copies of the starter categories in the same
    transaction, so nobody ends up registered with nothing to log against. The
    user row is flushed before them: the categories point at it by foreign key,
    and SQLAlchemy will not order the inserts on its own without a mapped
    relationship between the two.

    The boolean is True when this call created the row. Safe to call on every
    /start: an already registered chat keeps its row, with the display name
    refreshed if Telegram now reports a different one.
    """
    with SessionLocal() as session:
        user = session.get(User, chat_id)

        if user is None:
            user = User(chat_id=chat_id, name=name)
            session.add(user)

            try:
                session.flush()
            except IntegrityError:
                session.rollback()
                return session.get(User, chat_id), False

            session.add_all(build_default_categories(chat_id))
            session.commit()
            session.refresh(user)
            return user, True

        if user.name != name:
            user.name = name
            session.commit()
            session.refresh(user)

        return user, False


def get_currency(chat_id: int) -> str:
    """The currency new expenses for this chat should be recorded in."""
    with SessionLocal() as session:
        user = session.get(User, chat_id)
        return user.currency if user else DEFAULT_CURRENCY


def set_currency(chat_id: int, code: str) -> None:
    """Change the currency for expenses recorded from now on.

    Expenses already recorded keep the currency stored on them, so changing
    this never rewrites history.
    """
    with SessionLocal() as session:
        user = session.get(User, chat_id)
        if user is None:
            return
        user.currency = code
        session.commit()
