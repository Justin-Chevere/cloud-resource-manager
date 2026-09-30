from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db import Base, get_db
from app.main import app
from app.runtime import FakeRuntime


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    # A fresh in-memory database per test. StaticPool keeps one connection alive,
    # otherwise every new connection would see its own empty in-memory database.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False)


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # Not used as a context manager on purpose: that would run the lifespan,
    # which creates the real controlplane.db file and starts the reconciler.
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def runtime() -> FakeRuntime:
    return FakeRuntime()
