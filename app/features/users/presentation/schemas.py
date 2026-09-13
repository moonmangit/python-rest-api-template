from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.features.users.domain.model import UserRole, UserStatus


class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    role: UserRole = UserRole.MEMBER


class UserUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    role: UserRole | None = None
    status: UserStatus | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: UserRole
    status: UserStatus
    timezone: str
    default_currency: str
