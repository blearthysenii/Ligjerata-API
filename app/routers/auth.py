import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.database import get_db


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Email or password is incorrect",
    headers={"WWW-Authenticate": "Bearer"},
)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_token_response(user: models.User) -> schemas.TokenResponse:
    from app.core.admin import is_admin_email

    token, expires_in = create_access_token(str(user.id))

    return schemas.TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=schemas.UserResponse(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            is_active=user.is_active,
            is_admin=is_admin_email(user.email),
            created_at=user.created_at,
        ),
    )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication token is invalid or expired",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        user_id = int(decode_access_token(token))
    except (jwt.InvalidTokenError, TypeError, ValueError):
        raise credentials_error

    user = db.query(models.User).filter(
        models.User.id == user_id
    ).first()

    if not user or not user.is_active:
        raise credentials_error

    return user


@router.post(
    "/register",
    response_model=schemas.TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: schemas.UserRegister,
    db: Session = Depends(get_db),
):
    email = normalize_email(str(payload.email))
    existing_user = db.query(models.User).filter(
        models.User.email == email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = models.User(
        full_name=payload.full_name,
        email=email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    db.refresh(user)

    return create_token_response(user)


@router.post(
    "/login",
    response_model=schemas.TokenResponse,
)
def login(
    payload: schemas.UserLogin,
    db: Session = Depends(get_db),
):
    email = normalize_email(str(payload.email))
    user = db.query(models.User).filter(
        models.User.email == email
    ).first()

    if not user or not verify_password(
        payload.password,
        user.hashed_password,
    ):
        raise INVALID_CREDENTIALS

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive",
        )

    return create_token_response(user)


@router.get(
    "/me",
    response_model=schemas.UserResponse,
)
def me(
    current_user: models.User = Depends(get_current_user),
):
    from app.core.admin import is_admin_email

    return schemas.UserResponse(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        is_active=current_user.is_active,
        is_admin=is_admin_email(current_user.email),
        created_at=current_user.created_at,
    )
