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
- `/set_currency`: set the currency new expenses are recorded in (defaults to USD)
- `/cancel`: abandon whichever flow is in progress

## Details

Amounts can be written as addition expressions, so `12.50 + 3` works, and they are stored as exact decimals. Categories nest one level deep. Any step of any flow can be cancelled, by button or with `/cancel`.

Renaming a category keeps the expenses logged against it, because an expense points at the category row and not at its name. The starter category sits last in the pickers only because it is called `Other`, so renaming it drops it back into alphabetical order with everything else.

Deleting a category never deletes an expense. A subcategory's expenses move up to its parent. A top-level category's move wherever you choose, and deleting it takes its subcategories with it. A category that holds expenses with nowhere to move them, because it is your only one, cannot be deleted. Every delete is confirmed first with a count of what it will affect, and nothing you confirm can be undone.

Expenses are browsed newest first, six to a page. Opening one shows a card with its amount, category, description and date, each editable on its own. An edit is written the moment you send it and the card redraws underneath, so you can fix two fields on one expense in a single visit. Editing an amount keeps the currency the expense was recorded in.

The card uses the same layout as the confirmation you get after adding an expense, and both come from `handlers/summary.py`, so the two cannot drift apart. The heading says what just happened, which is where an edit reports itself instead of on a line of its own. That confirmation also carries an Edit button onto the card, for when you spot that the amount is one digit out. The button names the expense itself, so it keeps working later and across restarts, with no open conversation needed.

Each expense stores the currency it was recorded in, so `/set_currency` affects new expenses only and never rewrites what is already logged. The symbol goes before or after the amount by the convention for that currency: `$12.50`, but `12.50 zł`.

`/spending` totals one month by category. A top-level category's figure is its whole branch: what was logged against it directly plus everything in its subcategories, since that is what a category total means to the person reading it. Where a parent holds both, the direct part gets a row of its own, so the subcategory rows and the figure above them visibly add up. Rows run biggest first, which is the one place the bot departs from the alphabetical order its pickers use, because a report is read to find where the money went.

The report opens on the current month and the buttons move one month at a time, back as far as the oldest expense and forward no further than the current month. The month on display rides in the callback data rather than in conversation state, so the buttons still work after a restart. Because an expense keeps the currency it was recorded in, nothing is added across currencies: a month holding more than one gets a table each, captioned with its code.

## Setup

### Environment variables

| Variable       | Description                                                                  |
| -------------- | ---------------------------------------------------------------------------- |
| `TG_TOKEN`     | Telegram bot token                                                           |
| `DATABASE_URL` | Full Postgres connection URL                                                 |
| `TIMEZONE`     | IANA timezone for dates, e.g. `America/Toronto`. Optional, defaults to `UTC` |

Telegram does not tell the bot where you are, so `TIMEZONE` is what "today" means when you log an expense. Leave it unset and the bot uses UTC, which will file an evening expense under tomorrow if you are west of it. A value the bot does not recognise stops it at startup instead of quietly falling back to UTC.

A missing `DATABASE_URL` also stops the bot at startup, with a clear error. Managed Postgres providers usually set it for you, so a deploy needs no database configuration of its own. Both `postgres://` and `postgresql://` URLs work. Locally, put these variables in a `.env` file; on a hosting platform, set them in the project settings.

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

Autogenerate drafts a revision by diffing the models against the live database, and it is not authoritative. It renders a renamed column as a drop plus an add, which destroys that column's data, so review every generated file before applying it. Revisions in `migrations/versions/` are source code and belong in git.

The connection URL reaches Alembic from `DATABASE_URL` through `migrations/env.py`, so `alembic.ini` holds no credentials.

On deploy, run `alembic upgrade head` as the platform's pre-deploy command, so the schema is in place before the new container starts.

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
