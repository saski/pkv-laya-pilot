# PKV Laya pilot — results

Run date: 2026-11-01. Decision: **do not integrate this Laya reranker into Arnesto on the present evidence.**

Laya ran successfully on the local M1 Pro. Its tested relevance question worsened average ranking and added latency. Reducing output to three passages saved context, but almost the same reduction was available without Laya. This is a bounded pilot result, not a general verdict on all Laya tasks or a statistically established production regression.

## Dataset and comparison boundary

The frozen corpus contains 103 curated Markdown documents (500,843 bytes), drawn from notes, maps, projects, portfolio, governance and entry guides. Raw inbox sources were excluded from retrieval.

The 20 cases comprise **13 adaptations of verified historical user requests and 7 newly authored practical PKV questions**. They are not 20 verbatim historical queries. Only 13 defensible historical candidates were found; the user was asked how to complete the set, and the stated working assumption was to label new questions explicitly. Some historical adaptations deliberately narrow a larger request to its reusable knowledge component; Q03 and Q05 substantially change the original task's scope. There are 15 answerable or scoped-partial cases and 5 no-answer/source-mismatch/current-status controls. Quality denominators exclude those five controls; latency and context include all twenty.

The existing search is an agent procedure. The baseline is a frozen, reproducible metadata/lexical approximation of wiki-query, with bilingual keywords fixed before model scoring. It is not an instrumented Codex/Hermes turn. Both arms receive the same 10 candidate documents and the same 22-line, token-bounded excerpts. Laya changes only their order. This does not measure final generated answers, agent planning, tool round trips, later full-page reads, or paid model billing.

## Quality and context

| Method | Any useful source | Direct source | Source recall | nDCG | Mean context tokens | Context vs lexical top 5 |
|---|---:|---:|---:|---:|---:|---:|
| Lexical top 5 | 14/15 | 13/15 | 67.4% | 0.738 | 1605 | 0.0% |
| Laya top 5 | 13/15 | 13/15 | 60.1% | 0.591 | 1608 | -0.2% |
| Lexical top 3 | 13/15 | 13/15 | 55.6% | 0.714 | 932 | 41.9% |
| Laya top 3 | 13/15 | 13/15 | 46.7% | 0.554 | 927 | 42.2% |

Any useful source counts grade 1 support or grade 2 direct evidence. Direct source counts at least one grade-2 source. Recall is the macro fraction of labelled sources retrieved; many sources overlap, so recall is not the proportion of questions answered. nDCG rewards putting stronger evidence earlier. Labels were reviewed and adjudicated before Laya scoring, but they are agent-reviewed judgments, not user-certified ground truth.

The direct-passage hit rate is 10/15 for lexical top 5 and 10/15 for Laya top 5. The gap from document-level source hits reflects excerpts that omit necessary details. Candidate recall@10 is 89.4%; reranking cannot repair sources missing from that pool.

Laya top 3 reduces context by 42.2% versus lexical top 5. The lexical top-3 control already saves 41.9%. At the same three-result limit, Laya saves only 0.5% in this run and has lower recall/nDCG. At five results Laya actually sends slightly more tokens. The context-saving claim therefore belongs mainly to selecting fewer passages, not to the model.

Counts use the same o200k_base tokenizer and the exact serialized snippets a downstream model would receive. Laya separately processed 88,694 input tokens for one complete 20-query round, measured with its own tokenizer. Those counts are not directly additive to o200k tokens and are not paid API usage; they show that downstream context reduction does not eliminate local reranker work.

Paired bootstrap over the 15 answerable queries (10,000 samples) gives an nDCG@5 difference of -0.146, with a 95% interval [-0.321, 0.027]. It crosses zero. This small curated set, which includes related queries, does not establish a general performance difference; it does not provide evidence to justify adoption either.

## Latency and resources

| Measurement | Lexical | Laya |
|---|---:|---:|
| Resident median per query | 4.6 ms | 647.0 ms |
| Resident p95 per query | 14.3 ms | 750.5 ms |

Five randomized paired rounds produced 100 measured queries per arm. Candidates are batched within one query (batch size 4), never across separate queries. MPS is synchronized before/after measured inference. Resident timings include retrieval, excerpt selection, ranking and context packing; corpus/index loading and model loading are separate. OS caches were warm. No attempt was made to evict filesystem caches or claim cold-start search latency.

- Frozen corpus/index load: 197.6 ms.
- Model download: 10.70 s.
- First model load during installation: 6.68 s; cached load for evaluation: 4.12 s.
- First installation prediction: 2.01 s for two unrelated smoke-test passages; this is not a full PKV query measurement.
- Peak process RSS: 2.54 GiB. MPS driver allocation at end: 2.53 GiB. These are separate, overlapping memory accounting measures; do not add them as total physical RAM.
- Project footprint at completion: approximately 2.2 GiB including environment and isolated caches.
- Model-input truncations: 0 across 1,000 scored passages; unknown truncation records: 0.
- Ranking changes across the five repetitions: lexical 0, Laya 0 queries.

## What changed in individual queries

- **Q05 improved:** the experiment-before-adoption query promotes Learning Before Building from lexical rank 6 to Laya rank 1. This is the clearest useful semantic correction in the set.
- **Q03 regressed:** the overload-control source starts at lexical rank 1 and leaves Laya's top 5. A career map and the Obsidian pilot guide move ahead of the relevant technical note.
- **Q14 illustrates corpus noise:** several notes repeat the token-productivity claim in both summary and body despite different titles. The final labels count the actual repeated evidence, avoiding an unfair penalty for retrieving a differently named duplicate. Cleaning such duplicated metadata/content is a separate possible improvement, not something modified in this pilot.
- **Q20 is a retrieval miss for both arms:** the NotebookLM promotion policy is in the guide, README and promotion policy, but none enters the candidate pool. The metadata-first approximation overweights incidental NotebookLM/review strings. A stronger body/phrase fallback or direct guide routing should be evaluated before adding a reranker. This is a limitation of the approximation, not proof that the existing interactive agent would miss the answer.
- **Q06, Q07 and Q09 expose excerpt limits:** the expected note is retrieved but its selected passage omits parts of the Dafny/Lean, budget-guarantee or TypeScript detail. Better section selection or one follow-up source read may matter more than ranking.

## Historical versus newly authored cases

| Slice | Answerable cases | Lexical nDCG@5 | Laya nDCG@5 |
|---|---:|---:|---:|
| Historical adaptations | 8 | 0.796 | 0.597 |
| New practical questions | 7 | 0.671 | 0.584 |

Both slices have lower observed nDCG under Laya. The five no-answer controls were retained to expose source and freshness boundaries, but neither arm has an abstention detector. Ranking an unrelated note is not evidence that an answer is supported. No probability threshold was tuned on this set.

| No-answer control | Highest Laya relevance probability |
|---|---:|
| Q04 | 0.5438 |
| Q08 | 0.0068 |
| Q10 | 0.1500 |
| Q12 | 0.1181 |
| Q13 | 0.0765 |

## Decision against the preregistered criteria

- Preserve top-5 quality: **not met** in observed recall/nDCG and any-useful-source hit rate.
- Compact top 3 retains baseline top-5 source coverage while saving at least 20% context: context threshold met, **coverage condition not met**.
- Advantage over lexical top 3: **not met**; the control saves almost the same context with better ranking metrics.
- Resident p95 below one second: **met**.

Keep the experiment available in GitHub for a future decision; the local installation was selected for removal after remote verification. Arnesto's shared routing and runtime configuration remains unchanged. The most justified next experiment is improving candidate/section retrieval and evaluating on more genuine, self-contained user queries with reviewed expected evidence. A different Laya prompt, checkpoint, tuning or retrieval strategy would require a new evaluation set rather than retuning this one until it passes.

## Reproducibility and verification

- Laya 0.4.20; Python 3.11.15; PyTorch 2.15.0; Transformers 5.22.1.
- Model: convaiinnovations/laya-multilingual at `e4e9ddf21a7b1903b7acffd8814ad4307bf63a67`.
- Weights SHA-256: `9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204` (643,835,514 bytes).
- Project dependencies are pinned in uv.lock. The run records fingerprints for code, protocol, dataset, corpus manifest and lockfile.
- Four behavior checks for metrics/ranking passed; Ruff correctness/import checks passed.
- 100 paired observations completed with identical candidate sets, finite probabilities, stable rankings and no truncated model inputs.
- All run fingerprints still match. All 103 source-document hashes still match the original vault. Arnesto's pre-existing changed-file list was preserved.
- Evaluation used the local checkpoint and offline Hugging Face/Transformers settings. No vault content was submitted to model APIs. No persistent server, MCP entry, startup task or integration was installed.

Artifacts: [query inventory](queries.md), [per-query CSV](per-query.csv), [measured JSON](evaluation.json), [protocol](../../PROTOCOL.md), [sanitized reviewed dataset](../../datasets/pkv-2026-11-01/queries.json).
