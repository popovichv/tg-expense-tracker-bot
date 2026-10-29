from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from models.models import User


def get_or_create_user(chat_id: int, name: str) -> tuple[User, bool]:
    """Return the user for this chat, creating the row only if it is missing.

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
                session.commit()
            except IntegrityError:
                session.rollback()
                return session.get(User, chat_id), False
            session.refresh(user)
            return user, True

        if user.name != name:
            user.name = name
            session.commit()
            session.refresh(user)

        return user, False
