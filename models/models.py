from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    # Telegram chat ids are supplied by Telegram, not generated here, and can
    # exceed 32 bits (group chats are large negatives), so: BigInteger, and no
    # autoincrement sequence.
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str]


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str]
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    chat_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.chat_id"), nullable=True
    )


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.chat_id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    description: Mapped[str | None]
    spent_at: Mapped[date] = mapped_column(default=date.today)
    currency: Mapped[str] = mapped_column(default="CAD")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
