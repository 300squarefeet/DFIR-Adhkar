"""Adhkar command-line tools.

Usage:
    uv run python -m adhkar.cli bootstrap --org-name "Acme" \\
        --admin-email admin@acme.test --admin-password '…'
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from typing import NoReturn

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from adhkar.auth.password import hash_password, validate_password_policy
from adhkar.core.settings import get_settings
from adhkar.db.engine import create_engine
from adhkar.db.models import Organization, User, UserOrgMembership
from adhkar.services.seed import seed_default_profiles


def _slugify(name: str) -> str:
    out = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    return out[:63] or "org"


async def _bootstrap(
    org_name: str, admin_email: str, admin_password: str, admin_display_name: str
) -> None:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session, session.begin():
        existing_org = (
            await session.execute(select(Organization).where(Organization.name == org_name))
        ).scalar_one_or_none()
        if existing_org:
            org = existing_org
            print(f"[bootstrap] org '{org_name}' already exists ({org.id})")
        else:
            org = Organization(name=org_name, slug=_slugify(org_name))
            session.add(org)
            await session.flush()
            print(f"[bootstrap] created org '{org_name}' ({org.id})")

        existing_user = (
            await session.execute(select(User).where(User.email == admin_email))
        ).scalar_one_or_none()
        if existing_user:
            user = existing_user
            print(f"[bootstrap] user '{admin_email}' already exists ({user.id})")
        else:
            validate_password_policy(admin_password, hibp=False)
            user = User(
                email=admin_email,
                display_name=admin_display_name,
                password_hash=hash_password(admin_password),
                status="active",
                default_org_id=org.id,
            )
            session.add(user)
            await session.flush()
            print(f"[bootstrap] created admin '{admin_email}' ({user.id})")

        profile_map = await seed_default_profiles(session, org.id)
        print(f"[bootstrap] seeded profiles: {sorted(profile_map.keys())}")

        existing_mem = (
            await session.execute(
                select(UserOrgMembership).where(
                    UserOrgMembership.user_id == user.id,
                    UserOrgMembership.organization_id == org.id,
                )
            )
        ).scalar_one_or_none()
        if not existing_mem:
            session.add(
                UserOrgMembership(
                    user_id=user.id,
                    organization_id=org.id,
                    profile_id=profile_map["org-admin"],
                )
            )
            print("[bootstrap] bound admin to org-admin profile")
        print("[bootstrap] done.")
    await engine.dispose()


def main(argv: list[str] | None = None) -> NoReturn:
    parser = argparse.ArgumentParser(prog="adhkar", description="Adhkar admin CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    bs = sub.add_parser("bootstrap", help="seed first org + admin user")
    bs.add_argument("--org-name", required=True)
    bs.add_argument("--admin-email", required=True)
    bs.add_argument("--admin-password", required=True)
    bs.add_argument("--admin-display-name", default="Administrator")

    args = parser.parse_args(argv)
    if args.cmd == "bootstrap":
        asyncio.run(
            _bootstrap(
                args.org_name,
                args.admin_email,
                args.admin_password,
                args.admin_display_name,
            )
        )
        sys.exit(0)
    sys.exit(2)


if __name__ == "__main__":
    main()
