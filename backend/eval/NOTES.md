# Retrieval eval — notes and decisions

Run: `python -m eval.run_retrieval_eval --out eval/results/NAME.json -v`
(host: set `QDRANT_URL`, `DATA_DIR`, `DATABASE_URL`, `REDIS_URL`; the LLM is never called.)
Set: `retrieval_eval.jsonl` — 152 items (108 answerable, 38 restricted, 6 off-topic), zh + en.

## History (served-context recall = evidence is in the chunks actually given to the LLM)

| step | served-context recall | notes |
|---|---|---|
| baseline: retrieve 3, give 3 | 0.88 | `results/baseline.json` |
| retrieve 10, give 5, + neighbour chunks | 0.95 | `task2_retrieve10_serve5_neighbors.json` |
| + `SERVE_FLOOR=0.40` (wider context pool, same gate) | 0.98 | `task2b_serve_floor_040.json` |
| + structured chunks / section-aware prefix / table chunks | 0.97 | `task34_structured_chunks.json` (scores shifted: 3 borderline items fell below the 0.44 gate) |
| + recalibrated gate (`RELEVANCE_THRESHOLD` 0.42, `DENY_MARGIN` 0.15) | **0.98**, allow-decision 1.00 | `task34b_recalibrated.json` |
| +11 exact-term items (codes/acronyms/figures), same system | 0.98 | `task5_before_hybrid.json` — all 11 already served (rank 1-3) |

Safety metrics were 0 throughout: no entitled-chunk violations, and no restricted evidence
in any answer context.

## Decision: hybrid (dense + keyword) retrieval — not built

Offline experiment on the live collection (348 chunks): BM25 over the persona's *permitted*
chunks (latin tokens + CJK bigrams) fused with dense ranks by reciprocal-rank fusion;
metric = all evidence in the top-K fused chunks, 108 answerable items.

| | recall@3 | recall@5 |
|---|---|---|
| dense only (current) | 0.907 | 0.954 |
| BM25 only | 0.583 | 0.620 |
| RRF, equal weights, k=60 | 0.843 | 0.944 |
| RRF, k=10, sparse weight 0.15-0.5 (best region) | 0.898-0.907 | 0.963 |

Best case is +1 question out of 108 at @5 and nothing at @3 — within noise — while it would need
a Qdrant schema change (named dense + sparse vectors), a tokenizer, an ingestion change and a
re-seed. The questions are mostly paraphrased or cross-lingual, so keyword overlap is weak, and
dense recall@10 is already 0.99: the remaining misses are *ranking* problems, not candidate
recall problems (-> reranking, task 7).

Revisit hybrid if: the corpus grows by an order of magnitude, users start asking by ticket / case
/ rule IDs that dense search ranks poorly, or the exact-term items (`kind=exact`) start missing.
