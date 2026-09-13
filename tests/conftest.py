from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.features.auth.domain.model import (  # noqa: F401
    ApplicationGrant,
    AuditEvent,
    RefreshSession,
)
from app.features.spending_ledger.domain.model import (  # noqa: F401
    Attachment,
    Category,
    IdempotencyKey,
    LedgerRecord,
)
from app.features.users.domain import User  # noqa: F401


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)

    with testing_session() as session:
        yield session

    Base.metadata.drop_all(bind=engine)
