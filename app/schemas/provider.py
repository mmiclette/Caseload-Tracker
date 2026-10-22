from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ProviderRole


class ProviderCreate(BaseModel):
    name: str
    role: ProviderRole
    phone: str | None = None
    email: str | None = None
    # Write-only — never echoed back. If omitted, this Provider is created
    # without login credentials (fine for a role that doesn't authenticate
    # directly); a password can't currently be added later through this
    # schema (there's no "set password" route yet — see CLAUDE.md).
    password: str | None = None


class ProviderUpdate(BaseModel):
    name: str | None = None
    role: ProviderRole | None = None
    phone: str | None = None
    email: str | None = None


class ProviderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider_id: int
    name: str
    role: ProviderRole
    phone: str | None
    email: str | None
    created_at: datetime
    updated_at: datetime
