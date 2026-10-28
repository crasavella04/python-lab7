import os

# Тесты работают с отдельной БД tasks_test. app.config читает DATABASE_URL при импорте,
# поэтому переменную нужно выставить до импорта приложения.
TEST_DATABASE_URL = os.environ.setdefault(
    "TEST_DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5432/tasks_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import make_url, text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app import models  # noqa: E402, F401  регистрирует модели в Base.metadata
from app.db import Base, get_session  # noqa: E402
from app.main import app  # noqa: E402


async def ensure_database(url: str) -> None:
    """Создаёт тестовую БД, если её ещё нет (подключаемся к служебной БД postgres)."""
    db_url = make_url(url)
    admin = create_async_engine(
        db_url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    async with admin.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": db_url.database},
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{db_url.database}"'))
    await admin.dispose()


@pytest.fixture(scope="session")
async def engine():
    """Один движок на всю сессию тестов; схема пересоздаётся с нуля."""
    await ensure_database(TEST_DATABASE_URL)
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables(engine):
    """Каждый тест начинается на пустых таблицах, счётчики id сброшены."""
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE users, tasks RESTART IDENTITY CASCADE"))


@pytest.fixture
async def client(engine):
    """HTTP-клиент к приложению, get_session подменён на сессию тестовой БД."""
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def user(client):
    response = await client.post(
        "/users", json={"email": "alice@example.com", "name": "Alice"}
    )
    assert response.status_code == 201
    return response.json()
