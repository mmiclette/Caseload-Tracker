"""
Portable column type helpers.

`PortableJSON` is SQLAlchemy's dialect-agnostic JSON type. It renders as
JSON on Postgres and as VARIANT-backed JSON on Snowflake via
snowflake-sqlalchemy, without touching JSONB (Postgres-only) anywhere.
"""

from sqlalchemy import JSON

PortableJSON = JSON
