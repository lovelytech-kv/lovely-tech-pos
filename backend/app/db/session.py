from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import settings

class Base(DeclarativeBase):
    pass

@lru_cache(maxsize=1)
def get_engine():
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)

@lru_cache(maxsize=1)
def get_session_factory():
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)

