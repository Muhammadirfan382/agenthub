"""Create an account and give it a role in an organization.

    .venv/Scripts/python.exe -m scripts.create_user --email you@example.com \\
        --name "Your Name" --organization "Your Workspace" --role owner

There is no public sign-up: accounts are created here, deliberately. The
password is typed at a prompt, never passed as an argument, so it does not end
up in shell history, process listings or logs.
"""

import argparse
import asyncio
import getpass
import sys

from app.core.config import get_settings
from app.core.errors import ApiError
from app.db.session import create_engine, create_session_factory
from app.repositories import identity_repository
from app.schemas.enums import ROLES, Role
from app.services import auth_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an AgentHub account.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--organization",
        required=True,
        help="Organization name. It is created if no organization has that name yet.",
    )
    parser.add_argument("--role", default="owner", choices=list(ROLES))
    parser.add_argument("--timezone", default="UTC")
    return parser.parse_args()


def prompt_password() -> str:
    first = getpass.getpass("Password: ")
    second = getpass.getpass("Repeat password: ")
    if first != second:
        print("The passwords do not match.", file=sys.stderr)
        raise SystemExit(1)
    return first


async def run(args: argparse.Namespace, password: str) -> int:
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    try:
        async with factory() as session:
            slug = auth_service.slugify(args.organization)
            organization = await identity_repository.get_organization_by_slug(session, slug)
            created_organization = organization is None
            if organization is None:
                organization = await auth_service.create_organization(
                    session, name=args.organization
                )

            user = await identity_repository.get_user_by_email(session, args.email)
            created_user = user is None
            if user is None:
                user = await auth_service.create_user(
                    session,
                    email=args.email,
                    name=args.name,
                    password=password,
                    timezone=args.timezone,
                )

            role: Role = args.role
            await auth_service.add_member(session, organization=organization, user=user, role=role)
            await session.commit()

        print(
            f"{'Created' if created_user else 'Used existing'} account {user.email} "
            f"and added it to {'new ' if created_organization else ''}"
            f"organization '{organization.name}' as {role}."
        )
        return 0
    except ApiError as error:
        print(f"Failed: {error.message}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()


def main() -> int:
    args = parse_args()
    return asyncio.run(run(args, prompt_password()))


if __name__ == "__main__":
    raise SystemExit(main())
