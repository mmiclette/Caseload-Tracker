"""
Application configuration.

Connection strings are read from environment variables (or a local .env file
for developer convenience). In production this app reads DATABASE_URL from
AWS Secrets Manager via the container's injected environment — no
credentials are ever hardcoded here.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg://cocm:cocm_local_dev@localhost:5432/cocm_registry"
    )
    environment: str = "local"

    # JWT signing key for Provider authentication (see app/core/security.py).
    # This is a credential, same as database_url above: read from the
    # environment locally and from AWS Secrets Manager in production, never
    # hardcoded for a real deployment. The literal below is a dev-only
    # placeholder, same spirit as the docker-compose Postgres password.
    secret_key: str = "dev-only-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # Monthly Time Tracker is org-configurable per CLAUDE.md — some
    # organizations don't track it at all. This is a plain global settings
    # flag rather than a per-org database row: multi-tenancy is planned
    # (a future Organization entity, one row per NeuroFlow customer org —
    # see CLAUDE.md's Monthly Time Tracker section) but not built yet, so
    # there's no per-org row for this to live on today. When Organization
    # exists, this flag moves onto it as a per-org column instead.
    monthly_time_tracker_enabled: bool = True


settings = Settings()
