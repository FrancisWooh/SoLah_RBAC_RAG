"""Mint a long-lived JWT for the read-only `auditor` identity, to put in the
Authorization header of the WorkBuddy MCP connection (an MCP client config has
a static header, so the normal 8-hour login token is not enough).

The token only works on the /mcp tools (all read-only). It does NOT work on the
REST admin API, which requires platform_admin. Treat it like a password: it is
printed once, never stored by the server; revoke by rotating JWT_SECRET (which
also logs everyone out) or by removing the `auditor` role from the user.

Usage:  python mint_audit_token.py [--days 30] [--username auditor]
"""

import argparse

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import create_access_token
from app.models.user import User


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--username", default="auditor")
    args = ap.parse_args()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == args.username))
        if user is None:
            raise SystemExit(f"user '{args.username}' not found - run seed_data.py first")
        print(create_access_token({"sub": str(user.id)}, expires_minutes=args.days * 24 * 60))


if __name__ == "__main__":
    main()
