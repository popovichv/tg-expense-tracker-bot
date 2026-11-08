from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, MetaData, Numeric, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from utils import clock

# Named constraints, so a migration that has to alter or drop one has a stable
# identifier to reference instead of a name the database invented.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


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
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.chat_id"))


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.chat_id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    description: Mapped[str | None]
    spent_at: Mapped[date] = mapped_column(default=clock.today)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
