"""Retrieval evaluation against the real seeded vector store.

Usage (inside the backend container, or on the host with QDRANT_URL / DATA_DIR set):
    python -m eval.run_retrieval_eval [--set eval/retrieval_eval.jsonl] [--out eval/results/NAME.json] [-v]

Each item: question, persona (seed_data user), doc_id (gold doc), evidence
(verbatim snippet(s) that answer it), expected allow|deny, kind, lang.

Metrics, answerable items (expected=allow with a gold doc):
  chunk recall@k  - the evidence text is inside one of the top-k retrieved chunks
                    (k=3 is what the LLM is actually given today: TOP_K)
  all-evidence@k  - for multi-fact items, EVERY evidence snippet is in the top-k chunks
  doc hit@k       - the gold document appears in the top-k (looser; for reference)
  MRR@10          - 1/rank of the first chunk containing the evidence
  served-context  - the evidence is in the chunks the pipeline really passes to the LLM
Decision accuracy (answer_text_query with the extractive MockLLM, so no API cost):
  allow items -> decision == allow; deny items -> decision == deny;
  offtopic -> allow with no citations.
Safety (must be 0): any retrieved/cited chunk the persona is not entitled to, or
an archived document / a `forbidden_doc` being returned.
The LLM is never called here; this measures retrieval and the allow/deny decision only.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from app.services import query_service
from app.services.embeddings.factory import get_embedder
from app.services.llm.mock_llm import MockLLM
from app.services.vectorstore.base import PermissionContext
from app.services.vectorstore.factory import get_vector_store
from seed_data import PERMANENT_ROLE_GRANTS, USERS, manifest_doc_id

KS = (1, 3, 5, 10)
HERE = Path(__file__).parent


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _persona(username: str) -> PermissionContext:
    u = next(u for u in USERS if u["username"] == username)
    return PermissionContext(set(PERMANENT_ROLE_GRANTS[username]), u["clearance"], set(u["compartments"]))


def _manifest():
    from app.core.config import settings

    return {manifest_doc_id(m["id"]): m for m in json.loads((Path(settings.data_dir) / "manifest.json").read_text())}


def _entitled(m: dict, perm: PermissionContext) -> bool:
    return (
        m["status"] == "active"
        and bool(set(m["allowed_roles"]) & perm.roles)
        and m["required_clearance"] <= perm.clearance
        and set(m["compartments"]) <= perm.compartments
    )


def run(eval_path: Path, verbose: bool) -> dict:
    items = [json.loads(line) for line in eval_path.read_text().splitlines() if line.strip()]
    manifest, embedder, store = _manifest(), get_embedder(), get_vector_store()
    query_service.get_llm = lambda: MockLLM()  # decision logic only; never call a paid LLM here

    rows, leaks = [], []
    for it in items:
        perm = _persona(it["persona"])
        evidences = it["evidence"] if isinstance(it["evidence"], list) else ([it["evidence"]] if it["evidence"] else [])
        vec = embedder.embed_query(it["question"])
        hits = store.search(vec, perm, top_k=max(KS))
        texts = [_norm(h.text) for h in hits]

        def found_in(k):  # evidence snippets present in the top-k chunks of the gold doc
            pool = " ".join(t for h, t in zip(hits[:k], texts[:k]) if h.doc_id == it["doc_id"])
            return [_norm(e) in pool for e in evidences]

        row = dict(id=it["id"], kind=it["kind"], lang=it["lang"], persona=it["persona"], q=it["question"], expected=it["expected"])
        if it["doc_id"] and it["expected"] == "allow" and evidences:
            for k in KS:
                f = found_in(k)
                row[f"any@{k}"], row[f"all@{k}"] = any(f), all(f)
            row["doc@3"] = any(h.doc_id == it["doc_id"] for h in hits[:3])
            rank = next((i + 1 for i, (h, t) in enumerate(zip(hits, texts)) if h.doc_id == it["doc_id"] and any(_norm(e) in t for e in evidences)), None)
            row["rank"], row["rr"] = rank, (1 / rank if rank else 0.0)

        result = query_service.answer_text_query(it["question"], perm)
        row["decision"] = result.decision
        served = " ".join(_norm(c.snippet) for c in result.citations if c.doc_id == it["doc_id"])
        if it["doc_id"] and it["expected"] == "allow" and evidences:
            row["served"] = all(_norm(e) in served for e in evidences)
        all_served = " ".join(_norm(c.snippet) for c in result.citations)
        row["n_cite"] = len(result.citations)
        if it["expected"] == "deny" and evidences:
            # the restricted fact must never reach the answer context, whatever the decision label says
            row["exposed"] = any(_norm(e) in all_served for e in evidences)
        if it["kind"] == "offtopic":
            row["decision_ok"] = result.decision == "allow" and not result.citations
        else:
            row["decision_ok"] = result.decision == it["expected"]

        # safety: everything returned must be entitled and active
        returned = {h.doc_id for h in hits} | {c.doc_id for c in result.citations}
        bad = [d for d in returned if d in manifest and not _entitled(manifest[d], perm)]
        if it.get("forbidden_doc") and it["forbidden_doc"] in returned:
            bad.append(it["forbidden_doc"])
        if bad:
            leaks.append((it["id"], it["persona"], bad))
        row["top_docs"] = [h.doc_id for h in hits[:3]]
        rows.append(row)

    return dict(rows=rows, leaks=leaks, summary=_summarize(rows, leaks))


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def _summarize(rows, leaks):
    ans = [r for r in rows if "rank" in r]
    s = dict(n_items=len(rows), n_answerable=len(ans), leaks=len(leaks))
    for k in KS:
        s[f"chunk_recall@{k}"] = _mean(r[f"any@{k}"] for r in ans)
    s["all_evidence@3"] = _mean(r["all@3"] for r in ans)
    s["all_evidence@5"] = _mean(r["all@5"] for r in ans)
    s["doc_hit@3"] = _mean(r["doc@3"] for r in ans)
    s["MRR@10"] = _mean(r["rr"] for r in ans)
    s["served_context_recall"] = _mean(r["served"] for r in ans if "served" in r)
    for exp in ("allow", "deny"):
        sel = [r for r in rows if r["expected"] == exp and r["kind"] != "offtopic"]
        s[f"decision_acc_{exp}"] = _mean(r["decision_ok"] for r in sel)
    den = [r for r in rows if "exposed" in r]
    s["restricted_exposed"] = sum(r["exposed"] for r in den)
    s["restricted_n"] = len(den)
    s["restricted_allowed_with_citations"] = sum(1 for r in den if r["decision"] == "allow" and r["n_cite"] > 0)
    s["decision_acc_offtopic"] = _mean(r["decision_ok"] for r in rows if r["kind"] == "offtopic")
    by = defaultdict(list)
    for r in ans:
        by[("kind", r["kind"])].append(r)
        by[("lang", r["lang"])].append(r)
    s["by_group"] = {f"{a}={b}": dict(n=len(v), recall3=_mean(x["any@3"] for x in v), recall10=_mean(x["any@10"] for x in v), served=_mean(x.get("served", False) for x in v)) for (a, b), v in sorted(by.items())}
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default=str(HERE / "retrieval_eval.jsonl"))
    ap.add_argument("--out")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    res = run(Path(a.set), a.verbose)
    s = res["summary"]
    print(f"items={s['n_items']} answerable={s['n_answerable']} LEAKS={s['leaks']}")
    print("chunk recall@1/3/5/10: " + " / ".join(f"{s[f'chunk_recall@{k}']:.2f}" for k in KS))
    print(f"all-evidence@3={s['all_evidence@3']:.2f} @5={s['all_evidence@5']:.2f}  doc-hit@3={s['doc_hit@3']:.2f}  MRR@10={s['MRR@10']:.2f}  served-context recall={s['served_context_recall']:.2f}")
    print(f"restricted items: evidence EXPOSED in answer context = {s['restricted_exposed']}/{s['restricted_n']} (must be 0); answered 'allow' using other docs = {s['restricted_allowed_with_citations']}")
    print(f"decision accuracy: allow={s['decision_acc_allow']:.2f} deny={s['decision_acc_deny']:.2f} offtopic={s['decision_acc_offtopic']:.2f}")
    for g, v in s["by_group"].items():
        print(f"  {g:22} n={v['n']:3d} recall@3={v['recall3']:.2f} recall@10={v['recall10']:.2f} served={v['served']:.2f}")
    if res["leaks"]:
        print("LEAKS:", res["leaks"])
    misses = [r for r in res["rows"] if ("served" in r and not r["served"]) or not r["decision_ok"]]
    print(f"\n{len(misses)} items with a miss (served-context or decision):")
    for r in misses[: (200 if a.verbose else 25)]:
        print(f"  {r['id']:8} [{r['kind']}/{r['lang']}] {r['persona']:6} exp={r['expected']} got={r['decision']} rank={r.get('rank')} top={r['top_docs']} | {r['q'][:70]}")
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
        print("saved", a.out)


if __name__ == "__main__":
    sys.exit(main())
