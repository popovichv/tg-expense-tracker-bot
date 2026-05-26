from sqlalchemy import select, or_
from database import SessionLocal
from models import Category


def get_top_level_categories(chat_id: int) -> list[Category]:
    with SessionLocal() as session:
        result = session.execute(
            select(Category).where(
                or_(
                    Category.chat_id == chat_id,
                    Category.chat_id == None,
                ),
                Category.parent_id == None,
            )
        )
        return result.scalars().all()


def add_category(name: str, chat_id: int | None = None, parent_id: int | None = None) -> Category:
    with SessionLocal() as session:
        category = Category(name=name, chat_id=chat_id, parent_id=parent_id)
        session.add(category)
        session.commit()
        session.refresh(category)
        return category
