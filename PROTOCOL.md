# PKV Laya retrieval pilot — preregistered protocol

Date: 2026-11-01. This protocol is frozen before scoring the 20 evaluation queries.

## Question

Does a local Laya reranker improve retrieval quality or reduce the context needed by a downstream agent enough to justify its latency and maintenance cost?

## Scope and provenance

- Standalone project: `<pilot-checkout>`; no Arnesto, OmniRoute, Codex, Hermes or vault configuration changes.
- Read-only corpus: curated Markdown under `notes`, `maps`, `projects`, `portfolio`, plus the vault guide and governance files needed for operational questions. Raw inbox material is excluded from retrieval.
- Freeze the corpus file manifest, hashes, evaluation queries, source provenance, relevance labels, prompt and package/model versions before evaluation.
- Recover distinct historical user requests. Keep the original text and source location. Any adaptation into a standalone retrieval question must be explicitly labelled. Only 13 defensible historical candidates were found. The user was asked how to complete the set; absent a preference, the working assumption is to add seven practical questions grounded in existing PKV content, explicitly labelled as new. This is a 20-query practical pilot, not a 20-query historical production log. Report the historical/new slices separately.
- No model training, prompt search or threshold tuning on these queries. The installation smoke test is unrelated to the vault evaluation.

## Baseline

The current search is an agent procedure, not an existing callable search service. Implement a reproducible lexical approximation of `wiki-query`: title/alias matches, then tags, then summaries/index information, with section/body matches as fallback. Report this distinction prominently. Freeze any bilingual search keywords before model scores are seen; apply identical keywords and candidates to both arms. Use query-token IDF overlap weighted 8 for title/alias, 4 for tags, 2 for summary, with a 100-point exact-title bonus; body overlap breaks metadata ties and supplies candidates with no metadata match. These weights are an explicit operational approximation, not a previously deployed ranking formula. Load a frozen corpus and metadata index once; report that setup cost separately from resident retrieval.

Retrieve up to 10 candidate documents and extract the same bounded passage from each, with title, summary, source path and line range. Passage selection uses only the query and lexical matches, never gold labels. Exact matches remain available in the candidate pool, although the experimental reranker may move them. Any relevant source absent from the candidate set remains a miss; do not inject gold documents into retrieval. Take the highest lexical-overlap 22-line window on a 10-line stride, serialize path/title/summary/window, and cap it at 450 o200k tokens before an excerpt-end marker. Both arms receive that same passage.

## Treatment and controls

1. Lexical top 5: principal baseline.
2. Laya top 5: equal-count ranking comparison.
3. Lexical top 3: cheap context-reduction control.
4. Laya top 3: proposed compact context.

Use the pinned `laya-multilingual` checkpoint on MPS. Ask one binary relevance question for each query/passage pair. Sort by the probability of relevance, not by the model's confidence in either yes or no. Break ties with the original order. Keep all candidates available; there is no probability threshold or hard deletion. Batch candidates within each query; do not batch separate user queries to understate interactive latency.

## Metrics

- Quality: answer-source recall@3/@5, hit@3/@5, MRR and nDCG@3/@5. Record candidate recall@10 to distinguish retrieval misses from ranking failures. Relevance is manually reviewed from source evidence, without model scores. Grade 2 means direct source evidence and grade 1 useful supporting evidence; recall counts both. Unanswerable cases are excluded from recall/nDCG denominators and reported separately. Ranking alone is not abstention: neither arm is being given a trained no-answer detector.
- Also distinguish direct-source hit (at least one grade-2 source) from direct-passage hit (at least one selected excerpt judged to contain direct evidence). A correct document can have an insufficient excerpt. Known relevant documents outside the candidate pool remain retrieval misses. Reviewer suggestions were adjudicated before scoring, with both original suggestions and final rationales retained.
- Context: count the actual serialized selected snippets using `o200k_base`, a fixed comparison tokenizer. This is a token-count proxy, not a measured Codex invoice. Compare equal counts and top-3 vs top-5 for both arms. Report full-document counts separately only as a diagnostic.
- Latency: separate download, model load, first prediction and resident-model queries. Run five randomized paired repetitions of all 20 queries, synchronize MPS before/after inference, report median and p95 end-to-end retrieval plus prioritization. Include parsing, passage extraction and packing; exclude answer generation and historical-query curation. Report index/setup cost separately if cached.
- Reliability: record model-input truncation, invalid probabilities, ranking stability across repetitions and peak memory.
- Uncertainty: paired bootstrap 95% intervals over queries; this small curated sample is a pilot, not evidence of general production reliability.

## Adoption criteria

Recommend integration only if Laya top 5 preserves baseline quality, and a compact Laya top 3 retains baseline top-5 source coverage with at least 20% fewer context tokens. It must offer a useful advantage over lexical top 3, not merely select fewer documents. Target warm p95 below 1 second per query for this interactive use. Any condition not met is a reason to keep the current path and report why; do not retune the held-out set until it passes.

## Reporting limits

This measures retrieval and context, not final answer quality or complete Codex/Hermes turn latency. Historical requests adapted for retrieval are not a production query log. Labels are source-based reviewer judgments, not user-certified ground truth. Candidate pooling can miss other relevant documents; record known limitations and errors. All evaluation and model inference stay local.
