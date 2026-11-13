"""Sign-in with short access tokens and a refresh token in an HttpOnly cookie.

Every signed-in device has one AuthSession row. The device holds two tokens:

- An access token (a JWT, 15 minutes) that the frontend sends as
  "Authorization: Bearer ...". Every request checks that its session still
  exists, so deleting the session signs the device out at once.
- A refresh token in an HttpOnly cookie that JavaScript can't read. The frontend
  calls POST /auth/refresh with it to get a new access token. Each refresh
  replaces the refresh token. If an old one comes back later, someone may have
  copied it, so the session is ended.
"""

import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

import jwt
from email_validator import EmailNotValidError
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from psycopg.errors import UniqueViolation
from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.db.models.auth_session import AuthSession
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
ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)
SESSION_LIFETIME = timedelta(days=30)

REFRESH_COOKIE_NAME = "refresh_token"
# The browser only sends the cookie to /auth/*, not with every API request.
REFRESH_COOKIE_PATH = "/auth"
# Browsers drop Secure cookies on plain http, except on localhost in most of them.
# Set REFRESH_COOKIE_SECURE=false for local http setups where the cookie gets lost.
REFRESH_COOKIE_SECURE = os.environ.get("REFRESH_COOKIE_SECURE", "true") != "false"
# Two tabs may refresh with the same cookie at once. The slower one sends the
# token that the faster one just replaced. That is not theft, so allow it briefly.
REFRESH_REUSE_GRACE = timedelta(seconds=30)

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


def hash_refresh_secret(secret: str) -> str:
    # The secret is 32 random bytes, so a fast hash is enough (unlike passwords).
    return hashlib.sha256(secret.encode()).hexdigest()


def new_refresh_secret(auth_session: AuthSession) -> str:
    """Give the session a new refresh token and return the cookie value for it."""
    secret = secrets.token_urlsafe(32)
    auth_session.refresh_token_hash = hash_refresh_secret(secret)
    # The session ID lets /refresh find the session even for an old, replaced token.
    return f"{auth_session.id}.{secret}"


def start_session(user_id: UUID, db: Session) -> tuple[AuthSession, str]:
    """Create a session and return it with its refresh cookie value."""
    now = datetime.now(UTC)

    db.execute(
        delete(AuthSession).where(
            AuthSession.user_id == user_id,
            AuthSession.expires_at < now,
        )
    )
    auth_session = AuthSession(
        id=uuid4(),
        user_id=user_id,
        expires_at=now + SESSION_LIFETIME,
    )
    cookie_value = new_refresh_secret(auth_session)
    db.add(auth_session)
    db.commit()

    return auth_session, cookie_value


def create_access_token(auth_session: AuthSession) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(auth_session.user_id),
        "sid": str(auth_session.id),
        "iat": now,
        "exp": now + ACCESS_TOKEN_LIFETIME,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def set_refresh_cookie(response: Response, value: str, expires_at: datetime) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=value,
        # Starlette needs exactly UTC, not the offset Postgres hands back
        expires=expires_at.astimezone(UTC),
        path=REFRESH_COOKIE_PATH,
        secure=REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )


def token_response(auth_session: AuthSession, response: Response) -> Token:
    response.headers["Cache-Control"] = "no-store"
    return Token(
        access_token=create_access_token(auth_session),
        expires_in=int(ACCESS_TOKEN_LIFETIME.total_seconds()),
    )


def refresh_failed() -> HTTPException:
    """A 401 that also deletes the refresh cookie in the browser."""
    cleared = Response()
    clear_refresh_cookie(cleared)
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session expired, please sign in again",
        headers={
            "set-cookie": cleared.headers["set-cookie"],
            "Cache-Control": "no-store",
        },
    )


def parse_refresh_cookie(value: str | None) -> tuple[UUID, str] | None:
    if not value:
        return None
    session_id, _, secret = value.partition(".")
    try:
        return UUID(session_id), secret
    except ValueError:
        return None


def get_current_session(
    token: Annotated[str, Depends(oauth2_scheme)], db: DbSession
) -> AuthSession:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["sub", "sid", "exp"]},
        )
        session_id = UUID(payload["sid"])
    except (InvalidTokenError, ValueError, TypeError, AttributeError) as e:
        raise unauthorized("Invalid or expired token") from e

    auth_session = db.get(AuthSession, session_id)

    # No row means the device signed out, or was signed out by another device
    if auth_session is None or auth_session.expires_at <= datetime.now(UTC):
        raise unauthorized("Invalid or expired token")

    return auth_session


def get_current_user(
    auth_session: Annotated[AuthSession, Depends(get_current_session)],
) -> User:
    return auth_session.user


def check_current_password(user: User, password: str) -> None:
    if not verify_password(password, user.password_hash):
        # 400, not 401: a 401 would make the frontend think it was signed out
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


CurrentSession = Annotated[AuthSession, Depends(get_current_session)]
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
    response: Response,
    db: DbSession,
) -> Token:
    user = authenticate_user(form.username, form.password, db)

    if user is None:
        raise unauthorized("Incorrect email or password")

    auth_session, cookie_value = start_session(user.id, db)
    set_refresh_cookie(response, cookie_value, auth_session.expires_at)

    return token_response(auth_session, response)


@router.post("/refresh", response_model=Token)
def refresh(
    response: Response,
    db: DbSession,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> Token:
    parsed = parse_refresh_cookie(refresh_token)
    if parsed is None:
        raise refresh_failed()
    session_id, secret = parsed

    # Lock the row so two refreshes of the same session run one after the other
    auth_session = db.scalar(
        select(AuthSession).where(AuthSession.id == session_id).with_for_update()
    )
    now = datetime.now(UTC)
    if auth_session is None or auth_session.expires_at <= now:
        raise refresh_failed()

    presented_hash = hash_refresh_secret(secret)

    if secrets.compare_digest(presented_hash, auth_session.refresh_token_hash):
        auth_session.previous_refresh_token_hash = auth_session.refresh_token_hash
        auth_session.refreshed_at = now
        cookie_value = new_refresh_secret(auth_session)
        db.commit()
        set_refresh_cookie(response, cookie_value, auth_session.expires_at)
        return token_response(auth_session, response)

    just_replaced = (
        auth_session.previous_refresh_token_hash is not None
        and auth_session.refreshed_at is not None
        and now - auth_session.refreshed_at < REFRESH_REUSE_GRACE
        and secrets.compare_digest(
            presented_hash, auth_session.previous_refresh_token_hash
        )
    )
    if just_replaced:
        # Another tab refreshed a moment ago and the browser already has its new
        # cookie. Hand out an access token but leave that cookie alone.
        db.rollback()
        return token_response(auth_session, response)

    # An old refresh token came back. It may have been stolen, so end the session.
    db.delete(auth_session)
    db.commit()
    raise refresh_failed()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(auth_session: CurrentSession, response: Response, db: DbSession) -> None:
    db.delete(auth_session)
    db.commit()
    clear_refresh_cookie(response)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_everywhere(user: CurrentUser, response: Response, db: DbSession) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.commit()
    clear_refresh_cookie(response)


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
    data: PasswordChange, auth_session: CurrentSession, db: DbSession
) -> None:
    user = auth_session.user
    check_current_password(user, data.current_password)

    if data.new_password == data.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )

    user.password_hash = hash_password(data.new_password)

    # Sign out every other device, but keep the one that changed the password
    db.execute(
        delete(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.id != auth_session.id,
        )
    )
    db.commit()
