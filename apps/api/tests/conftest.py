from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.db.session import engine, get_db
from api.main import app


@pytest.fixture
def db() -> Iterator[Session]:
    """A database session that undoes everything after the test.

    The routes call commit(). With "create_savepoint" each commit only closes a
    savepoint, and the outer transaction rolls all of it back at the end.
    """
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    """An API client that uses the test session for every request."""
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()
