# Telegram Expense Tracker Bot

A Python-based Telegram bot with the PTB library and a SQLAlchemy ORM layer. Built for personal expense tracking and spending analytics.

## Stack

- **Python 3.15**
- **[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)** — bot framework with conversation handlers and inline keyboards
- **SQLAlchemy 2.1** — ORM with mapped column syntax
- **PostgreSQL** — relational database backend (via `psycopg` 3)

## Features

- `/start` — register user
- `/add_category` — create top-level categories or subcategories
- `/list_categories` — view your category tree
- `/manage_categories` — rename or delete a category or subcategory
- `/add_expense` — log an expense with category, amount, optional description, and date
- `/manage_expenses` — browse your expenses and edit or delete one
- `/set_currency` — set the currency new expenses are recorded in (defaults to USD)
- `/cancel` — abandon whichever flow is in progress

Amounts support addition expressions (e.g. `12.50 + 3`) and are stored as exact decimals. Categories support one level of nesting. Every step of every flow can be cancelled, by button or with `/cancel`.

Renaming a category keeps the expenses logged against it, which point at the row and not at the
name. The starter `Other` is listed last in the pickers by virtue of being called "Other", so
renaming it drops it back into alphabetical order with everything else.

Deleting a category never deletes an expense. A subcategory's expenses move up to its parent;
a top-level category's move wherever you choose, and deleting it takes its subcategories with
it. A category holding expenses with nowhere to move them — your only one — cannot be deleted.
Every delete is confirmed with a count of what it will affect first, and none of it undoes.

Expenses are browsed newest first, six to a page. Opening one shows a card with its amount,
category, description and date, each editable on its own. An edit is written the moment you
send it and the card redraws underneath, so fixing two fields on one expense is one visit
rather than two. Editing an amount keeps the currency the expense was recorded in.

The card is laid out exactly like the confirmation an expense is added with — one layout,
in `handlers/summary.py`, so the two cannot drift apart. Its heading says what just
happened, so an edit reports itself there rather than on a line of its own.

The confirmation `/add_expense` ends with carries an Edit button onto that same card, for the
amount typed one digit out. It keeps working later on, and across restarts, because the
button names the expense itself rather than relying on the conversation still being open.

Each expense stores the currency it was recorded in, so changing `/set_currency` affects new
expenses only and never rewrites what is already logged. The symbol is placed before or after
the amount according to the convention for that currency — `$12.50`, but `12.50 zł`.

## Setup

### Environment variables

| Variable       | Description                                          |
| -------------- | ---------------------------------------------------- |
| `TG_TOKEN`     | Telegram bot token                                   |
| `DATABASE_URL` | Full Postgres connection URL                         |
| `TIMEZONE`     | IANA timezone for dates, e.g. `America/Toronto`. Optional, defaults to `UTC` |

Telegram does not tell the bot where you are, so `TIMEZONE` is what "today" means when
logging an expense. Leave it unset and the bot uses UTC, which will file an evening expense
under tomorrow if you are west of it. An unrecognised value stops the bot at startup rather
than silently falling back.

`DATABASE_URL` is required — the bot stops at startup with a clear error if it is missing.
Managed Postgres providers generally inject it automatically, so no manual database
configuration is needed on deploy. Both `postgres://` and `postgresql://` URLs are accepted.
Create a `.env` file locally or set these in your deployment platform project settings.

### Run locally

```bash
pip install -r requirements.txt
alembic upgrade head
python main.py
```

### Database migrations

The schema is owned by [Alembic](https://alembic.sqlalchemy.org/), not by the app — `main.py`
does not create tables. Apply the current schema with:

```bash
alembic upgrade head
```

After changing anything in `models/`, generate a revision, **read it**, then apply it:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Autogenerate drafts a revision by diffing the models against the live database; it is not
authoritative. It renders a renamed column as a drop plus an add, which destroys that
column's data, so review every generated file before applying it. Revisions in
`migrations/versions/` are source code and belong in git.

The connection URL comes from `DATABASE_URL` via `migrations/env.py`, so `alembic.ini`
holds no credentials.

On deploy, run `alembic upgrade head` as the platform's **pre-deploy command**, so the
schema is in place before the new container starts.

## Project structure

```
handlers/       # PTB conversation and command handlers
repo/           # Database query functions
models/         # SQLAlchemy ORM models
utils/          # Standalone helpers (clock, currency, amounts)
migrations/     # Alembic environment and revisions
database.py     # Engine and session setup
config.py       # Environment variable loading and connection URL
main.py         # App entry point and job queue
alembic.ini     # Alembic config (no credentials; URL comes from env.py)
```
