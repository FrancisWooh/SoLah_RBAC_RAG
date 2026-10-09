"""One-off: compute prev_hash/record_hash for audit_logs rows written before
the hash-chain feature existed (see app/services/audit.py), so the whole
table — not just rows from here on — is covered by verify_audit_chain().

Safe to re-run: rows that already have both hashes are left untouched and
used as-is as the chain's starting point.

Usage: python backfill_audit_hash_chain.py
"""

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.audit_log import AuditLog
from app.services.audit import GENESIS_HASH, _compute_record_hash, hashed_fields_of


def backfill():
    db = SessionLocal()
    try:
        rows = db.scalars(select(AuditLog).order_by(AuditLog.id.asc())).all()

        prev_hash = GENESIS_HASH
        updated = 0
        for row in rows:
            if row.prev_hash is not None and row.record_hash is not None:
                prev_hash = row.record_hash
                continue

            row_fields = hashed_fields_of(row)
            row.prev_hash = prev_hash
            row.record_hash = _compute_record_hash(prev_hash, row_fields)
            prev_hash = row.record_hash
            updated += 1

        db.commit()
        print(f"Backfilled {updated} of {len(rows)} row(s).")
    finally:
        db.close()


if __name__ == "__main__":
    backfill()
