"""Database engine creation and session management."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker


def create_engine(url: str, **kwargs) -> AsyncEngine:
    """Create async SQLAlchemy engine."""
    return create_async_engine(
        url,
        echo=kwargs.get("echo", False),
        pool_size=kwargs.get("pool_size", 10),
        max_overflow=kwargs.get("max_overflow", 5),
        pool_pre_ping=True,
    )


def get_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create session factory bound to engine."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
