"""Ambiente do Alembic (equivalente ao Flyway/Liquibase do mundo Spring).

Diferença importante: o Alembic compara o Base.metadata (seus modelos) com o banco
e GERA o script de migração (`alembic revision --autogenerate`). Sempre revise o
arquivo gerado antes de commitar.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app import models  # noqa: F401  (importar registra as tabelas no metadata)
from app.config import get_settings
from app.database import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
