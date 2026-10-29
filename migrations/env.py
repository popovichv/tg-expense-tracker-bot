from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

from config import DATABASE_URL
from models.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# compare_server_default is off by default and would otherwise miss changes to
# the created_at default; compare_type catches column type changes.
COMPARE_OPTS = {"compare_type": True, "compare_server_default": True}


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **COMPARE_OPTS,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # The URL comes from config.DATABASE_URL, not from alembic.ini, so the
    # credentials stay in one place and never get committed. The engine is built
    # directly rather than through config.set_main_option(), because alembic.ini
    # is a ConfigParser file where a '%' in the URL -- as in a percent-escaped
    # password -- would be misread as string interpolation.
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            **COMPARE_OPTS,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
