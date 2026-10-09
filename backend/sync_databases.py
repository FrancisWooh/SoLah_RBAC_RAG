"""One-off sync of the registered department databases (data_sources) into the knowledge base.
Usage: docker compose exec backend python sync_databases.py
(The backend also does this automatically every DB_SYNC_INTERVAL seconds.)"""

from app.services.db_sync import run_db_sync

if __name__ == "__main__":
    for name, r in run_db_sync().items():
        print(f"== {name}")
        for label, items in (("added", r.added), ("updated", r.updated), ("removed", r.removed),
                             ("skipped", r.skipped), ("errors", r.errors)):
            for i in items:
                print(f"  {label:8} {i}")
        if not (r.changed or r.skipped or r.errors):
            print("  up to date")
