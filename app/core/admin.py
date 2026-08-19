import os

from fastapi import Depends, HTTPException, status

from app import models
from app.routers.auth import get_current_user


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_admin_emails() -> set[str]:
    return {
        normalize_email(email)
        for email in os.getenv("ADMIN_EMAILS", "").split(",")
        if email.strip()
    }


def is_admin_email(email: str) -> bool:
    return normalize_email(email) in get_admin_emails()


def require_admin(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if not is_admin_email(current_user.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )

    return current_user
