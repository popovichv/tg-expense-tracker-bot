# Telegram Expense Tracker Bot

A Python-based Telegram bot with the PTB library and a SQLAlchemy ORM layer. Built for personal expense tracking and spending analytics.

## Stack

- **[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)** — bot framework with conversation handlers and inline keyboards
- **SQLAlchemy 2.0** — ORM with mapped column syntax
- **PostgreSQL** — relational database backend (via `psycopg` 3)

## Features

- `/start` — register user
- `/add_category` — create top-level categories or subcategories
- `/list_categories` — view your category tree
- `/add_expense` — log an expense with category, amount, optional description, and date
- `/cancel` — abandon whichever flow is in progress

Amounts support addition expressions (e.g. `12.50 + 3`). Categories support one level of nesting. Every step of every flow can be cancelled, by button or with `/cancel`.

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
python main.py
```

## Project structure

```
handlers/       # PTB conversation and command handlers
repo/           # Database query functions
models/         # SQLAlchemy ORM models
database.py     # Engine and session setup
config.py       # Environment variable loading
main.py         # App entry point and job queue
```
