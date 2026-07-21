"""
Database layer: SQLAlchemy engine, session management, and connection pool.
Supports PostgreSQL with pgvector extension.
"""
import os
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import QueuePool

from config import Config

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    # 尊重 Config 拼装的 DB_* 变量（与 config.py 保持一致），
    # 仅在完全未配置任何数据库变量时才回落 SQLite 本地开发库
    if os.environ.get('DB_HOST') or os.environ.get('DB_PASSWORD'):
        DATABASE_URL = Config.DATABASE_URL
    else:
        DATABASE_URL = 'sqlite:///baiyun_culture.db'

# Infer engine kwargs from URL type
_is_postgres = DATABASE_URL.startswith('postgresql')
if _is_postgres:
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={'check_same_thread': False} if 'sqlite' in DATABASE_URL else {},
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
Base = declarative_base()


def init_extensions():
    """Enable pgvector extension on PostgreSQL."""
    if not DATABASE_URL.startswith('postgresql'):
        return
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()


def init_db():
    """Create all tables."""
    init_extensions()
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db_session():
    """Yield a DB session with automatic commit/rollback/close."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
