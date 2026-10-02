from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import StatementError

from app.models import Resource


def test_timestamps_come_back_as_utc(session_factory):
    with session_factory() as db:
        resource = Resource(name="web-1", image="nginx")
        db.add(resource)
        db.commit()
        db.refresh(resource)

        assert resource.created_at.tzinfo is UTC


def test_naive_timestamps_are_refused(session_factory):
    # A datetime without a time zone is ambiguous, so it's an error, not a guess.
    with session_factory() as db:
        db.add(Resource(name="web-1", image="nginx", created_at=datetime(2026, 1, 1)))
        with pytest.raises(StatementError):
            db.commit()
