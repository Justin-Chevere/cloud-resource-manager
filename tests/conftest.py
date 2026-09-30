from collections.abc import Callable, Iterator

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import security
from app.db import Base, get_db
from app.main import app
from app.models import Role, User
from app.runtime import FakeRuntime
from app.security import create_access_token, hash_password


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    # Real hashing costs 64 MiB and ~25 ms on purpose. Tests only need correctness.
    monkeypatch.setattr(
        security, "_hasher", PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    )


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
    """A client with no token: an anonymous caller."""

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
def make_user(session_factory: sessionmaker[Session]) -> Callable[..., User]:
    def _make_user(
        username: str,
        role: Role = Role.VIEWER,
        *,
        password: str = "test-password-123",
        is_active: bool = True,
    ) -> User:
        with session_factory() as db:
            user = User(
                username=username,
                password_hash=hash_password(password),
                role=role,
                is_active=is_active,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user

    return _make_user


@pytest.fixture
def client_as(client: TestClient, make_user: Callable[..., User]) -> Callable[..., TestClient]:
    """Build a client that sends a valid token for a new user with the given role."""

    def _client_as(role: Role, username: str | None = None) -> TestClient:
        user = make_user(username or role.value, role)
        token = create_access_token(user.id)
        return TestClient(app, headers={"Authorization": f"Bearer {token}"})

    return _client_as


@pytest.fixture
def viewer_client(client_as: Callable[..., TestClient]) -> TestClient:
    return client_as(Role.VIEWER)


@pytest.fixture
def operator_client(client_as: Callable[..., TestClient]) -> TestClient:
    return client_as(Role.OPERATOR)


@pytest.fixture
def admin_client(client_as: Callable[..., TestClient]) -> TestClient:
    return client_as(Role.ADMIN)


@pytest.fixture
def runtime() -> FakeRuntime:
    return FakeRuntime()
