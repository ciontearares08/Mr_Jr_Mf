import os
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from psycopg.errors import UniqueViolation
from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.db.models.user import User
from api.db.session import get_db
from api.schemas.user import LoginRequest, UserCreate, UserRead

# ROUTER SETUP
router = APIRouter()

# AUTH DEFAULTS
JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "agriculture-api"
JWT_AUDIENCE = "agriculture-web"
ACCESS_TOKEN_MINUTES = 30

password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash("dummy-password-needed-for-timing")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# AUTH FUNCTIONS
def hash_password(password: str) -> str:
    return password_hasher.hash(password)

def verify_password(password: str, stored_hash:str) -> bool:
    return password_hasher.verify(password,stored_hash)

def create_access_token(user_id: UUID) -> str:
    now = datetime.now(UTC)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


# ROUTER SETTINGS
@router.post(
    "/auth/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Register user"]
)
async def register_user(
    data: UserCreate,
    db: Annotated[Session, Depends(get_db)]
) -> UserRead:
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, UniqueViolation) and e.orig.diag.constraint_name == "users_email_key": # if email is taken in db
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            ) from e
        raise

    db.refresh(user)

    return UserRead.model_validate(user)