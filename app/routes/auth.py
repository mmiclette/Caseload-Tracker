from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.repositories.provider import ProviderRepository
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {"schema": LoginRequest.model_json_schema()},
                "application/x-www-form-urlencoded": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string", "description": "Provider email"},
                            "password": {"type": "string"},
                        },
                        "required": ["username", "password"],
                    }
                },
            },
        }
    },
)
async def login(request: Request, db: Session = Depends(get_db)):
    """
    Accepts BOTH content types on purpose (found by UI pressure testing
    2026-08-07): JSON {email, password} is the API contract the frontend
    and scripts use, and form-encoded username/password is what the OAuth2
    password flow advertised by get_current_provider's OAuth2PasswordBearer
    scheme sends — which is exactly what the interactive docs console's
    Authorize dialog posts. Supporting only JSON made that dialog fail with
    a 422, so any standards-compliant OAuth2 password client would fail the
    same way.
    """
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/x-www-form-urlencoded"):
        # Parsed with the stdlib rather than request.form(), which would
        # pull in python-multipart — the same stdlib-over-dependency call
        # as hashlib-instead-of-passlib in app/core/security.py.
        form = parse_qs((await request.body()).decode())
        email = (form.get("username") or form.get("email") or [""])[0]
        password = (form.get("password") or [""])[0]
        if not email or not password:
            raise HTTPException(status_code=422, detail="username and password are required")
    else:
        try:
            payload = LoginRequest.model_validate(await request.json())
        except (ValidationError, ValueError):
            raise HTTPException(status_code=422, detail="Invalid login payload")
        email, password = payload.email, payload.password

    repo = ProviderRepository(db)
    provider = repo.get_by_email(email)
    if (
        provider is None
        or not provider.hashed_password
        or not verify_password(password, provider.hashed_password)
    ):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(provider.provider_id)
    return TokenResponse(access_token=token, provider=provider)
