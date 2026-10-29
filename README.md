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
- `/add_expense` — log an expense with category, amount, optional description, and date
- `/cancel` — abandon whichever flow is in progress

Amounts support addition expressions (e.g. `12.50 + 3`) and are stored as exact decimals. Categories support one level of nesting. Every step of every flow can be cancelled, by button or with `/cancel`.

## Setup

### Environment variables

| Variable       | Description                  |
| -------------- | ---------------------------- |
| `TG_TOKEN`     | Telegram bot token           |
| `DATABASE_URL` | Full Postgres connection URL |

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
migrations/     # Alembic environment and revisions
database.py     # Engine and session setup
config.py       # Environment variable loading and connection URL
main.py         # App entry point and job queue
alembic.ini     # Alembic config (no credentials; URL comes from env.py)
```
