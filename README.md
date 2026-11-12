# Telegram Expense Tracker Bot

A Telegram bot for tracking personal expenses, built with python-telegram-bot and SQLAlchemy on top of Postgres.

## Stack

- Python 3.15
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot), using conversation handlers and inline keyboards
- SQLAlchemy 2.1, with the mapped column syntax
- PostgreSQL, via `psycopg` 3

## Commands

- `/start`: register
- `/add_category`: create a top-level category or a subcategory
- `/list_categories`: view your category tree
- `/manage_categories`: rename or delete a category or subcategory
- `/add_expense`: log an expense with category, amount, optional description, and date
- `/manage_expenses`: browse your expenses and edit or delete one
- `/spending`: one month's spending grouped by category, with buttons to step through earlier months
- `/cancel`: abandon whichever flow is in progress

## Behaviour

Send `12.50` or `12.50 coffee` with no command and the bot asks only for the category. Amounts can be written as addition expressions and are stored as exact decimals, so `10 + 5 lunch` is 15 spent on lunch. Whatever is left of the line becomes the description, and the date is today. A line starting with a digit that holds no usable amount is answered with how it should read, and anything else is left alone. Either way the confirmation is the same card, which carries an Edit button for a date other than today or an amount that is one digit out.

Categories nest one level deep, and renaming one keeps the expenses logged against it. Deleting one never deletes an expense: a subcategory's move up to its parent, a top-level category's move wherever you choose, and its subcategories go with it. A category whose expenses have nowhere to go, because it is your only one, cannot be deleted. Every delete is confirmed first with a count of what it affects, and nothing you confirm can be undone.

Expenses are browsed newest first, twelve to a page. Opening one shows the same card, with amount, category, description and date each editable on its own and written the moment you send it.

`/spending` totals one month by category, biggest first. A top-level figure covers the whole branch, and where a parent also holds expenses directly, that part gets a row of its own so the rows add up. The buttons move one month at a time, back as far as the oldest expense and no further forward than the current month.

Any step of any flow can be cancelled, by button or with `/cancel`. The Edit and month buttons carry what they need in their callback data, so they keep working across restarts.

## Setup

### Environment variables

| Variable       | Description                                                                  |
| -------------- | ---------------------------------------------------------------------------- |
| `TG_TOKEN`     | Telegram bot token                                                           |
| `DATABASE_URL` | Full Postgres connection URL                                                 |
| `TIMEZONE`     | IANA timezone for dates, e.g. `America/Toronto`. Optional, defaults to `UTC` |

Telegram does not tell the bot where you are, so `TIMEZONE` is what "today" means when you log an expense. Left unset it is UTC, which files an evening expense under tomorrow if you are west of it. A value the bot does not recognise stops it at startup.

### Run locally

```bash
pip install -r requirements.txt
alembic upgrade head
python main.py
```

### Database migrations

[Alembic](https://alembic.sqlalchemy.org/) owns the schema, not the app: `main.py` does not create tables. Apply the current schema with:

```bash
alembic upgrade head
```

After changing anything in `models/`, generate a revision, read it, then apply it:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Autogenerate drafts a revision by diffing the models against the live database and is not authoritative. It renders a renamed column as a drop plus an add, which destroys that column's data, so review every generated file before applying it. Revisions in `migrations/versions/` are source code and belong in git.

On deploy, run `alembic upgrade head` as the platform's pre-deploy command, so the schema is in place before the new container starts.

## Project structure

```
handlers/       # PTB conversation and command handlers
repo/           # Database query functions
models/         # SQLAlchemy ORM models
utils/          # Standalone helpers (clock, money, amounts)
migrations/     # Alembic environment and revisions
database.py     # Engine and session setup
config.py       # Environment variable loading and connection URL
main.py         # App entry point and job queue
alembic.ini     # Alembic config (no credentials; URL comes from env.py)
```
