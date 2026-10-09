"""On-disk embedding cache. Local/CPU embedding is slow (~3s per chunk), so
re-seeding must not recompute vectors for text that has not changed.
Keyed on (backend/model id, dim, sha256(text)). Document-side only: queries
are short and pass straight through."""

import hashlib
import json
import sqlite3
import threading


class CachedEmbedder:
    def __init__(self, inner, cache_key: str, path: str):
        self._inner = inner
        self._key = f"{cache_key}:{inner.dim}"
        self.dim = inner.dim
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS emb (k TEXT PRIMARY KEY, v TEXT)")

    def _k(self, text: str) -> str:
        return self._key + ":" + hashlib.sha256(text.encode()).hexdigest()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        keys = [self._k(t) for t in texts]
        with self._lock:
            found = {
                k: json.loads(v)
                for k in set(keys)
                if (row := self._db.execute("SELECT v FROM emb WHERE k=?", (k,)).fetchone()) and (v := row[0])
            }
        missing = [(k, t) for k, t in dict(zip(keys, texts)).items() if k not in found]
        if missing:
            vecs = self._inner.embed_texts([t for _, t in missing])
            with self._lock:
                self._db.executemany(
                    "INSERT OR REPLACE INTO emb VALUES (?,?)",
                    [(k, json.dumps(v)) for (k, _), v in zip(missing, vecs)],
                )
                self._db.commit()
            found.update({k: v for (k, _), v in zip(missing, vecs)})
        return [found[k] for k in keys]

    def embed_query(self, text: str) -> list[float]:
        inner_q = getattr(self._inner, "embed_query", None)
        return inner_q(text) if inner_q else self._inner.embed_texts([text])[0]
