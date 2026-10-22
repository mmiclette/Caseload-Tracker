"""
Bootstrap script: create the first Provider account with login credentials.

Every route in this API now requires a valid Provider token (see
app/core/deps.py's get_current_provider, applied at the router level in
app/main.py) — including POST /providers itself. That's the correct
default for "an internal authenticated tool, not a public site" (CLAUDE.md
tech stack notes), but it means the very first account can't be created
through the API: there's nobody logged in yet to create it. This script is
the standard way out of that chicken-and-egg problem (the same role a
`manage.py createsuperuser` plays in other frameworks) — it talks to the
repository layer directly, bypassing the API and its auth dependency.

Usage:
    python scripts/create_admin_provider.py "Jordan Lee" jordan@example.com a-real-password --role clinic_supervisor

Run this once per environment to get a first login, then create every
other Provider through POST /providers as that account.
"""

import argparse
import sys

from app.core.security import hash_password
from app.database import SessionLocal
from app.models.enums import ProviderRole
from app.models.provider import Provider
from app.repositories.provider import ProviderRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("email")
    parser.add_argument("password")
    parser.add_argument(
        "--role", default="clinic_supervisor", choices=[r.value for r in ProviderRole]
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        repo = ProviderRepository(db)
        if repo.get_by_email(args.email) is not None:
            print(f"A provider with email '{args.email}' already exists.", file=sys.stderr)
            sys.exit(1)

        provider = repo.create(
            Provider(
                name=args.name,
                role=ProviderRole(args.role),
                email=args.email,
                hashed_password=hash_password(args.password),
            )
        )
        print(f"Created provider #{provider.provider_id} ({provider.email}, role={provider.role.value}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
