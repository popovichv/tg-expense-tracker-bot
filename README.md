# Telegram Expense Tracker Bot

A Python-based Telegram bot with the PTB library and a SQLAlchemy ORM layer. Built for personal expense tracking and spending analytics.

## Stack

- **[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)** — bot framework with conversation handlers and inline keyboards
- **SQLAlchemy 2.0** — ORM with mapped column syntax
- **Azure SQL Server** — relational database backend (via `pyodbc` + ODBC Driver 18)

## Features

- `/start` — register user
- `/add_category` — create top-level categories or subcategories
- `/list_categories` — view your category tree
- `/add_expense` — log an expense with category, amount, optional description, and date

Amounts support addition expressions (e.g. `12.50 + 3`). Categories support one level of nesting.

## Setup

### Environment variables

| Variable      | Description               |
| ------------- | ------------------------- |
| `TG_TOKEN`    | Telegram bot token        |
| `DB_SERVER`   | Azure SQL server hostname |
| `DB_NAME`     | Database name             |
| `DB_USER`     | Database user             |
| `DB_PASSWORD` | Database password         |

Create a `.env` file locally or set these in your Railway project settings.

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
