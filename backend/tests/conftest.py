from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.database import AsyncSessionLocal, engine as _prod_engine
from app.main import app


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Provide a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSession() as session:
        yield session
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """HTTP client bound to the FastAPI app, using a fresh overridden DB."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.core import database as db_module

    # swap the app's DB factory to the in-memory test engine
    original_factory = db_module.AsyncSessionLocal

    async def _get_test_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[db_module.get_db] = _get_test_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
