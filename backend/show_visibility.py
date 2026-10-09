"""Show, per account, which database records it may see and why not.

Reads the records straight from the department databases (data_sources) and the
account from the users / user_roles tables, then applies the rule on its own,
independently of the retrieval code:

    allowed_roles hit  AND  required_clearance <= user.clearance  AND  compartments <= user.compartments

allowed_roles = the record's own roles if it has any, else the source's attach role.
Roles are the effective ones (permanent + active temporary/project grants); use
--permanent-only to ignore temporary grants.

Usage (from the project root):
  docker compose exec backend python show_visibility.py alice
  docker compose exec backend python show_visibility.py alice carol henry
  docker compose exec backend python show_visibility.py --all          # matrix of every account
  docker compose exec backend python show_visibility.py alice --source "HR Database" --only-denied
"""

import argparse
from datetime import datetime

from sqlalchemy import or_

from app.core.db import SessionLocal
from app.models.data_source import DataSource
from app.models.user import User
from app.models.user_role import UserRole
from app.services.db_sync import _as_list, fetch_rows


def effective_roles(db, user: User, permanent_only: bool) -> set[str]:
    q = db.query(UserRole.role_id).filter(UserRole.user_id == user.id, UserRole.status == "active")
    if permanent_only:
        q = q.filter(UserRole.source == "permanent")
    else:
        q = q.filter(or_(UserRole.end_at.is_(None), UserRole.end_at > datetime.utcnow()))
    return {r for (r,) in q}


def load_records(db, only_source: str | None) -> list[dict]:
    out = []
    for s in db.query(DataSource).order_by(DataSource.id):
        if only_source and only_source.lower() not in (s.name or "").lower():
            continue
        cfg, m = s.connection_config, s.permission_mapping or {}
        for row in fetch_rows(s):
            comps = [c.lower() for c in _as_list(row.get(m.get("compartment_column")))]
            roles = _as_list(row.get(m.get("roles_column"))) or _as_list(m.get("attach_roles"))
            clr = row.get(m.get("clearance_column"))
            out.append(dict(source=s.name, code=str(row[cfg["id_column"]]), title=row[cfg["title_column"]],
                            roles=roles, inherited=not _as_list(row.get(m.get("roles_column"))),
                            clearance=int(clr if clr is not None else m.get("default_clearance", 1)),
                            compartments=comps))
    return out


def check(rec: dict, roles: set[str], clearance: int, compartments: set[str]) -> list[str]:
    """Names of the gates that fail (empty list = visible)."""
    failed = []
    if not roles & set(rec["roles"]):
        failed.append("role")
    if rec["clearance"] > clearance:
        failed.append("clearance")
    if not set(rec["compartments"]) <= compartments:
        failed.append("compartment")
    return failed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("usernames", nargs="*")
    ap.add_argument("--all", action="store_true", help="matrix of all accounts")
    ap.add_argument("--source", help="only sources whose name contains this text")
    ap.add_argument("--only-denied", action="store_true", help="hide visible records")
    ap.add_argument("--permanent-only", action="store_true", help="ignore temporary / project role grants")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.username).all() if args.all else [
            u for n in args.usernames if (u := db.query(User).filter(User.username == n).one_or_none()) or print(f"no such user: {n}")]
        if not users:
            ap.error("give at least one username, or --all")
        records = load_records(db, args.source)
        grants = {u.username: effective_roles(db, u, args.permanent_only) for u in users}

        if args.all:
            print("✓ visible   role / C clearance / Z compartment = reason it is hidden\n")
            names = [u.username for u in users]
            print(f"{'record':9} {'clr':3} {'part':8} {'roles':34} " + " ".join(f"{n:>7}" for n in names))
            for r in records:
                cells = []
                for u in users:
                    f = check(r, grants[u.username], u.clearance, set(u.compartments))
                    cells.append("✓" if not f else "".join({"role": "R", "clearance": "C", "compartment": "Z"}[x] for x in f))
                roles = ",".join(r["roles"]) + ("*" if r["inherited"] else "")
                print(f"{r['code']:9} {r['clearance']:<3} {','.join(r['compartments']) or '-':8} {roles[:34]:34} " + " ".join(f"{c:>7}" for c in cells))
            print("\nR = role not matched, C = clearance too low, Z = compartment missing; * = role inherited from the source's attach role")
            return

        for u in users:
            roles = grants[u.username]
            print(f"\n=== {u.username}  roles={sorted(roles)}  clearance={u.clearance}  compartments={sorted(u.compartments)}")
            shown = hidden = 0
            last = None
            for r in records:
                f = check(r, roles, u.clearance, set(u.compartments))
                shown, hidden = shown + (not f), hidden + bool(f)
                if args.only_denied and not f:
                    continue
                if r["source"] != last:
                    print(f"  -- {r['source']}")
                    last = r["source"]
                why = "" if not f else "  <- " + ", ".join(
                    {"role": f"role (needs {'/'.join(r['roles'])})", "clearance": f"clearance (needs {r['clearance']})",
                     "compartment": f"compartment (needs {','.join(r['compartments'])})"}[x] for x in f)
                part = f"[{','.join(r['compartments'])}]" if r["compartments"] else "[normal]"
                print(f"  {'✓' if not f else '✗'} {r['code']:8} clr{r['clearance']} {part:11} {r['title']}{why}")
            print(f"  visible {shown} / hidden {hidden}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
