from datetime import datetime
from typing import Annotated
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, Field, field_validator

Password = Annotated[str, Field(min_length=12, max_length=256)]


class EmailInput(BaseModel):
    email: str = Field(...)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, raw_email: str) -> str:
        try:
            return normalize_email(raw_email)
        except EmailNotValidError as e:
            raise ValueError(f"Invalid email address: {e}") from e


class UserCreate(EmailInput):
    password: Password


class EmailChange(EmailInput):
    current_password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: Password


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str = Field(...)
    created_at: datetime = Field(...)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


def normalize_email(raw_email: str) -> str:
    result = validate_email(
        raw_email.strip(),
        check_deliverability=False,
    )
    return result.normalized.casefold()
