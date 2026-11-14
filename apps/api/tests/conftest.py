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


@pytest.fixture(scope="module")
def vcr_config() -> dict:
    """How pytest-recording records and replays DMI cassettes."""
    return {
        # The parameters download in parallel, so we match each request by
        # its URL and query and not by the order it arrives in.
        "match_on": ["method", "scheme", "host", "port", "path", "query"],
        # Stores the body as plain JSON text instead of gzip bytes.
        "decode_compressed_response": True,
        # A test can fetch the same month twice.
        "allow_playback_repeats": True,
    }
