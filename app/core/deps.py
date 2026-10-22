"""
Shared FastAPI dependencies.

get_current_provider is applied at the router level (dependencies=[...] on
each APIRouter, see app/main.py's included routers) rather than repeated on
every individual route function — CLAUDE.md's tech stack notes call this
"an internal authenticated tool, not a public site," so the default is
every business route requires a valid Provider token, with /auth/login and
/health as the only two exceptions.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models.provider import Provider
from app.repositories.provider import ProviderRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_current_provider(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> Provider:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_error
    try:
        payload = decode_access_token(token)
        provider_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise credentials_error

    provider = ProviderRepository(db).get_by_id(provider_id)
    if provider is None:
        raise credentials_error
    return provider
