import re
from logging.config import fileConfig

from alembic import context
from alembic.script import base as _script_base
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.database import Base
from app import models  # noqa: F401  enregistre les modèles dans Base.metadata

# Sur un disque exFAT, macOS crée des fichiers « ._nom.py » (métadonnées AppleDouble)
# qu'Alembic tenterait de charger comme migrations. On les ignore sans les supprimer.
# Filtre interne d'Alembic (vérifié en 1.20) : modifié seulement s'il existe.
if hasattr(_script_base, "_only_source_rev_file"):
    _script_base._only_source_rev_file = re.compile(r"(?!\.\#|__init__|\._)(.*\.py)$")
if hasattr(_script_base, "_sourceless_rev_file"):
    _script_base._sourceless_rev_file = re.compile(r"(?!\.\#|__init__|\._)(.*\.py)(c|o)?$")

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
