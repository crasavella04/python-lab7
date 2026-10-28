from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def reject_null(value):
    """Поле в *Update можно не передавать, но явный null для NOT NULL столбца — ошибка (422)."""
    if value is None:
        raise ValueError("field cannot be null")
    return value


# ---------- User ----------


class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    name: str = Field(min_length=1, max_length=100)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str
    created_at: datetime


class UserUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)

    _not_null = field_validator("email", "name")(reject_null)


# ---------- Task ----------


class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    done: bool = False
    owner_id: int


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    done: bool
    created_at: datetime
    owner_id: int


class TaskUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    # description можно очистить, передав null
    description: str | None = None
    done: bool | None = None

    _not_null = field_validator("title", "done")(reject_null)
