from sqlalchemy import func, select, or_
from database import SessionLocal
from models import Category


def get_top_level_categories(chat_id: int) -> list[Category]:
    with SessionLocal() as session:
        result = session.execute(
            select(Category)
            .where(
                or_(
                    Category.chat_id == chat_id,
                    Category.chat_id == None,
                ),
                Category.parent_id == None,
            )
            .order_by(Category.name)
        )
        return result.scalars().all()


def get_subcategories(parent_id: int, chat_id: int) -> list[Category]:
    with SessionLocal() as session:
        result = session.execute(
            select(Category)
            .where(
                Category.parent_id == parent_id,
                or_(
                    Category.chat_id == chat_id,
                    Category.chat_id == None,
                ),
            )
            .order_by(Category.name)
        )
        return list(result.scalars().all())


def find_duplicate(name: str, chat_id: int, parent_id: int | None) -> Category | None:
    """Return a category that would be indistinguishable from this one, if any.

    Scoped to one parent, so "Coffee" can live under both Food and Work, and
    matched case-insensitively, since names differing only in case produce
    buttons the user cannot tell apart. Shared categories count, because the
    user sees them in the same picker as their own.
    """
    with SessionLocal() as session:
        result = session.execute(
            select(Category).where(
                func.lower(Category.name) == name.strip().lower(),
                Category.parent_id == parent_id,
                or_(
                    Category.chat_id == chat_id,
                    Category.chat_id == None,
                ),
            )
        )
        return result.scalars().first()


def add_category(name: str, chat_id: int | None = None, parent_id: int | None = None) -> Category:
    with SessionLocal() as session:
        category = Category(name=name, chat_id=chat_id, parent_id=parent_id)
        session.add(category)
        session.commit()
        session.refresh(category)
        return category
