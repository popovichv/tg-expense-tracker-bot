from dataclasses import dataclass

from sqlalchemy import case, func, select

from database import SessionLocal
from models import Category
from repo.expense import count_for_categories, count_in_session, move_to_category

CATCH_ALL_CATEGORY = "Other"

DEFAULT_CATEGORIES = (
    "Food & Dining",
    "Transport",
    "Shopping",
    "Housing",
    "Entertainment",
    "Health & Fitness",
    "Hobbies",
    CATCH_ALL_CATEGORY,
)

CATCH_ALL_LAST = case(
    (func.lower(Category.name) == CATCH_ALL_CATEGORY.lower(), 1),
    else_=0,
)


@dataclass
class Deletion:
    """One category and everything that goes with it.

    `expense_count` is how many expenses the branch holds when this describes a
    deletion, and how many actually moved when it reports one that happened.
    """

    name: str
    subcategory_names: list[str]
    expense_count: int


def owned(category_id: int, chat_id: int):
    """A query for one category that will only ever match its owner's row.

    Category ids reach the repo from inline keyboard callback data, so they are
    matched together with the chat rather than trusted: a stale or forged button
    finds nothing instead of someone else's category.
    """
    return select(Category).where(
        Category.id == category_id,
        Category.chat_id == chat_id,
    )


def build_default_categories(chat_id: int) -> list[Category]:
    """The starter set a new user gets their own copies of.

    Returned unsaved so the caller can persist them in the same transaction
    that creates the user. They belong to that user like any other category,
    which is what lets them be renamed or deleted.
    """
    return [Category(name=name, chat_id=chat_id) for name in DEFAULT_CATEGORIES]


def get_top_level_categories(chat_id: int) -> list[Category]:
    with SessionLocal() as session:
        result = session.execute(
            select(Category)
            .where(
                Category.chat_id == chat_id,
                Category.parent_id == None,
            )
            .order_by(CATCH_ALL_LAST, Category.name)
        )
        return result.scalars().all()


def get_all_categories(chat_id: int) -> list[Category]:
    """Every category this chat has, parents and subcategories together.

    One read for callers that need to resolve a name or a parent anywhere in
    the tree, rather than a query per level.
    """
    with SessionLocal() as session:
        result = session.execute(
            select(Category)
            .where(Category.chat_id == chat_id)
            .order_by(CATCH_ALL_LAST, Category.name)
        )
        return list(result.scalars().all())


def get_subcategories(parent_id: int, chat_id: int) -> list[Category]:
    with SessionLocal() as session:
        result = session.execute(
            select(Category)
            .where(
                Category.parent_id == parent_id,
                Category.chat_id == chat_id,
            )
            .order_by(CATCH_ALL_LAST, Category.name)
        )
        return list(result.scalars().all())


def find_duplicate(
    name: str, chat_id: int, parent_id: int | None, exclude_id: int | None = None
) -> Category | None:
    """Return a category that would be indistinguishable from this one, if any.

    Scoped to one parent, so "Coffee" can live under both Food and Work, and
    matched case-insensitively, since names differing only in case produce
    buttons the user cannot tell apart.

    `exclude_id` leaves one row out of the comparison: the category being
    renamed, which matches itself and would otherwise make a change of case
    like "food" to "Food" look like a collision.
    """
    with SessionLocal() as session:
        query = select(Category).where(
            func.lower(Category.name) == name.strip().lower(),
            Category.parent_id == parent_id,
            Category.chat_id == chat_id,
        )

        if exclude_id is not None:
            query = query.where(Category.id != exclude_id)

        result = session.execute(query)
        return result.scalars().first()


def add_category(name: str, chat_id: int, parent_id: int | None = None) -> Category:
    with SessionLocal() as session:
        category = Category(name=name, chat_id=chat_id, parent_id=parent_id)
        session.add(category)
        session.commit()
        session.refresh(category)
        return category


def rename_category(category_id: int, chat_id: int, name: str) -> Category | None:
    """Give a category a new name, or return None if this chat has no such row."""
    with SessionLocal() as session:
        category = session.execute(owned(category_id, chat_id)).scalars().first()

        if category is None:
            return None

        category.name = name
        session.commit()
        session.refresh(category)
        return category


def describe_deletion(category_id: int, chat_id: int) -> Deletion | None:
    """What deleting this category would take with it, for the confirmation.

    Read only, and a snapshot: the delete counts again inside its own
    transaction rather than trusting these numbers, which were taken whenever
    the user happened to be shown them.
    """
    with SessionLocal() as session:
        category = session.execute(owned(category_id, chat_id)).scalars().first()

        if category is None:
            return None

        subcategories = session.execute(
            select(Category)
            .where(
                Category.parent_id == category.id,
                Category.chat_id == chat_id,
            )
            .order_by(CATCH_ALL_LAST, Category.name)
        )
        subcategories = list(subcategories.scalars().all())

        branch_ids = [category.id] + [sub.id for sub in subcategories]

        return Deletion(
            name=category.name,
            subcategory_names=[sub.name for sub in subcategories],
            expense_count=count_for_categories(branch_ids, chat_id),
        )


def delete_category_branch(
    category_id: int, chat_id: int, move_to: int | None = None
) -> Deletion | None:
    """Delete a category and its subcategories, moving their expenses first.

    One transaction, in the order the foreign keys will accept: expenses are
    repointed before the categories they referenced go, and the subcategories
    go before the parent they point at. Neither key cascades, so a wrong order
    is refused by the database rather than silently taking rows with it.

    `move_to` is where the branch's expenses land, and is required whenever it
    holds any -- without it there would be nowhere for them to go, so rather
    than destroy them the delete raises. It must be a category of this chat's
    from outside the branch, since one inside is about to stop existing.

    Returns what was actually deleted and how many expenses actually moved, or
    None when the category, or the destination, is not this chat's to touch.
    """
    with SessionLocal() as session:
        category = session.execute(owned(category_id, chat_id)).scalars().first()

        if category is None:
            return None

        subcategories = session.execute(
            select(Category).where(
                Category.parent_id == category.id,
                Category.chat_id == chat_id,
            )
        )
        subcategories = list(subcategories.scalars().all())

        name = category.name
        subcategory_names = [sub.name for sub in subcategories]
        branch_ids = [category.id] + [sub.id for sub in subcategories]

        if move_to is None:
            held = count_in_session(session, branch_ids, chat_id)
            if held:
                raise ValueError(
                    f"category {category_id} holds {held} expenses and no destination "
                    "was given for them"
                )
            moved = 0
        else:
            if move_to in branch_ids:
                raise ValueError(
                    f"category {move_to} is inside the branch being deleted"
                )

            destination = session.execute(owned(move_to, chat_id)).scalars().first()
            if destination is None:
                return None

            moved = move_to_category(session, branch_ids, move_to, chat_id)

        for sub in subcategories:
            session.delete(sub)

        session.flush()
        session.delete(category)
        session.commit()

        return Deletion(
            name=name,
            subcategory_names=subcategory_names,
            expense_count=moved,
        )
