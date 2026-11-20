from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def get_engine():
    url = get_settings().database_url
    options = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **options)


def get_db() -> Generator[Session, None, None]:
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as session:
        yield session
