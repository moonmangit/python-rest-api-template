from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import DateTime, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRole(StrEnum):
    GUEST = "guest"
    MEMBER = "member"
    ADMIN = "admin"


class UserStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    google_subject: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(
            UserRole,
            native_enum=False,
            length=6,
            values_callable=lambda roles: [role.value for role in roles],
        ),
        nullable=False,
        default=UserRole.MEMBER,
    )
    status: Mapped[UserStatus] = mapped_column(
        SqlEnum(
            UserStatus,
            native_enum=False,
            length=8,
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        nullable=False,
        default=UserStatus.ENABLED,
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    default_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="USD"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
