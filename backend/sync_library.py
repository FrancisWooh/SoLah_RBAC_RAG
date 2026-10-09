"""One-off library sync: pick up new / changed / removed files in DATA_DIR.
Usage: docker compose exec backend python sync_library.py
(The backend also does this automatically every LIBRARY_SYNC_INTERVAL seconds.)"""

from app.services.library_sync import run_sync

if __name__ == "__main__":
    r = run_sync()
    for label, items in (("added", r.added), ("updated", r.updated), ("archived", r.archived),
                         ("removed", r.removed), ("skipped", r.skipped), ("errors", r.errors)):
        for i in items:
            print(f"{label:9} {i}")
    print("up to date" if not (r.changed or r.skipped or r.errors) else "done")
