from pydantic import BaseModel

from app.schemas.provider import ProviderRead


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    provider: ProviderRead
