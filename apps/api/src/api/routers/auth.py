import os
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

import jwt
from email_validator import EmailNotValidError
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from psycopg.errors import UniqueViolation
from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.db.models.auth_token import AuthToken
from api.db.models.user import User
from api.db.session import get_db
from api.schemas.user import (
    EmailChange,
    PasswordChange,
    Token,
    UserCreate,
    UserRead,
    normalize_email,
)

# ROUTER SETUP
router = APIRouter(prefix="/auth", tags=["auth"])

# AUTH DEFAULTS
JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "agriculture-api"
JWT_AUDIENCE = "agriculture-web"
TOKEN_LIFETIME = timedelta(days=30)

password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash("dummy-password-needed-for-timing")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

DbSession = Annotated[Session, Depends(get_db)]


# AUTH FUNCTIONS
def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    return password_hasher.verify(password, stored_hash)


def unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def authenticate_user(email: str, password: str, db: Session) -> User | None:
    try:
        email = normalize_email(email)
    except EmailNotValidError:
        return None

    user = db.scalar(select(User).where(User.email == email))

    if user is None:
        # Hash anyway so response time doesn't reveal which emails exist
        verify_password(password, DUMMY_HASH)
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def create_access_token(user_id: UUID, db: Session) -> str:
    now = datetime.now(UTC)
    token_id = uuid4()

    db.execute(
        delete(AuthToken).where(
            AuthToken.user_id == user_id,
            AuthToken.expires_at < now,
        )
    )
    db.add(
        AuthToken(
            id=token_id,
            user_id=user_id,
            expires_at=now + TOKEN_LIFETIME,
        )
    )
    db.commit()

    payload = {
        "sub": str(user_id),
        "jti": str(token_id),
        "iat": now,
        "exp": now + TOKEN_LIFETIME,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def get_current_token(
    token: Annotated[str, Depends(oauth2_scheme)], db: DbSession
) -> AuthToken:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["sub", "jti", "exp"]},
        )
    except InvalidTokenError as e:
        raise unauthorized("Invalid or expired token") from e

    auth_token = db.get(AuthToken, UUID(payload["jti"]))

    if auth_token is None:  # the user has logged out with this token
        raise unauthorized("Invalid or expired token")

    return auth_token


def get_current_user(
    auth_token: Annotated[AuthToken, Depends(get_current_token)],
) -> User:
    return auth_token.user


def check_current_password(user: User, password: str) -> None:
    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )


def commit_unique_email(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        email_taken = (
            isinstance(e.orig, UniqueViolation)
            and e.orig.diag.constraint_name == "users_email_key"
        )
        if email_taken:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            ) from e
        raise


CurrentToken = Annotated[AuthToken, Depends(get_current_token)]
CurrentUser = Annotated[User, Depends(get_current_user)]


# ROUTES
@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def register_user(data: UserCreate, db: DbSession) -> UserRead:
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    commit_unique_email(db)
    db.refresh(user)

    return UserRead.model_validate(user)


@router.post("/token", response_model=Token)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> Token:
    user = authenticate_user(form.username, form.password, db)

    if user is None:
        raise unauthorized("Incorrect email or password")

    return Token(access_token=create_access_token(user.id, db))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(auth_token: CurrentToken, db: DbSession) -> None:
    db.delete(auth_token)
    db.commit()


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_everywhere(user: CurrentUser, db: DbSession) -> None:
    db.execute(delete(AuthToken).where(AuthToken.user_id == user.id))
    db.commit()


@router.get("/me", response_model=UserRead)
def read_current_user(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.patch("/email", response_model=UserRead)
def change_email(data: EmailChange, user: CurrentUser, db: DbSession) -> UserRead:
    check_current_password(user, data.current_password)

    user.email = data.email
    commit_unique_email(db)
    db.refresh(user)

    return UserRead.model_validate(user)


@router.patch("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: PasswordChange, auth_token: CurrentToken, db: DbSession
) -> None:
    user = auth_token.user
    check_current_password(user, data.current_password)

    user.password_hash = hash_password(data.new_password)

    # Log out every other device, but keep the one that changed the password
    db.execute(
        delete(AuthToken).where(
            AuthToken.user_id == user.id,
            AuthToken.id != auth_token.id,
        )
    )
    db.commit()
