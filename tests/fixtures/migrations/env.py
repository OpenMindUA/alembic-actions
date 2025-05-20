from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")

    # Use the dialect from environment variable if provided
    dialect_name = os.environ.get("ALEMBIC_DIALECT")

    # If a dialect is specified, modify the URL to use that dialect
    if dialect_name:
        # Create a dummy URL for SQL generation with the specified dialect
        url = f"{dialect_name}://"

    render_as_batch = (dialect_name == "sqlite" if dialect_name else False)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=render_as_batch,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Get the SQLAlchemy config section
    configuration = config.get_section(config.config_ini_section)

    # Use the dialect from environment variable if provided
    dialect_name = os.environ.get("ALEMBIC_DIALECT")
    if dialect_name:
        # Override the URL with the specified dialect
        configuration["sqlalchemy.url"] = f"{dialect_name}://"

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Set render_as_batch for SQLite dialect
        render_as_batch = (dialect_name == "sqlite" if dialect_name else False)

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=render_as_batch
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
