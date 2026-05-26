from datetime import date, datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    chat_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str]
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    chat_id: Mapped[int | None] = mapped_column(ForeignKey("users.chat_id"), nullable=True)


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("users.chat_id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    amount: Mapped[float]
    description: Mapped[str | None]
    spent_at: Mapped[date] = mapped_column(default=date.today)
    currency: Mapped[str] = mapped_column(default="CAD")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
