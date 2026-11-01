# PKV Laya Pilot

An inactive experiment comparing metadata/lexical PKV retrieval with local Laya relevance ranking. The pilot did **not** justify integrating Laya into Arnesto. Its code and evidence are retained here so the decision can be revisited without keeping the model or dependencies installed.

## What we learned

On 1 November 2026, the experiment used 103 curated Markdown documents and 20 queries: 13 adaptations of historical requests and 7 new practical questions. Fifteen queries had supporting evidence; five were no-answer controls. Five randomized rounds produced 100 measured queries per method.

| Top-5 measurement | Lexical baseline | With Laya |
|---|---:|---:|
| Mean source recall | 67.4% | 60.1% |
| Ranking quality, nDCG | 0.738 | 0.591 |
| Median resident latency | 4.6 ms | 647 ms |
| Mean downstream context | 1,605 tokens | 1,608 tokens |

Reducing the output to three passages saved 42.2% with Laya and 41.9% with the lexical baseline alone. The observed gain came mainly from returning fewer passages. The sample was small and the confidence interval for the ranking difference crossed zero; this was a local adoption decision, not a general verdict on Laya.

Read the [full report](archive/2026-11-01/report.md), [query inventory](archive/2026-11-01/queries.md), [per-query measurements](archive/2026-11-01/per-query.csv), and [protocol](PROTOCOL.md).

## Resume only when useful

The original environment was Apple M1 Pro, 32 GB RAM, Python 3.11, and Laya 0.4.20 on MPS. The complete installed environment and caches occupied about 2.2 GiB. Model weights alone were about 644 MB. Nothing downloads until the setup commands below are run.

1. Clone this private repository and inspect the archived decision first.
2. Follow [the development guide](DEVELOPMENT.md) to recreate the isolated environment and load a local PKV snapshot.
3. Recheck the retrieval baseline and labels against the current vault before drawing new conclusions.

The [sanitized evaluation dataset](datasets/pkv-2026-11-01/queries.json) retains standalone questions, search keywords and relevance labels. Original conversations, personal source text and candidate excerpts are not included. The corpus itself remains in the PKV. The [corpus manifest](datasets/pkv-2026-11-01/corpus-manifest.json) records relative document names, sizes and hashes used in the original experiment; it contains metadata, so this archive is private. A changed vault means a new experiment, not an exact replay.

## Boundaries

The baseline is a reproducible approximation of the metadata/section-first search procedure, not an instrumented Codex or Hermes conversation. The evaluation measures source retrieval, snippet context and local latency, not final answer quality or paid-model billing.

There is no Arnesto, OmniRoute, Codex or Hermes integration, and no background service. The original local environment was selected for removal after verifying this remote copy. The source PKV and agent configuration are outside the uninstall scope.

Laya is an external dependency: [upstream repository](https://github.com/NandhaKishorM/laya), [multilingual checkpoint](https://huggingface.co/convaiinnovations/laya-multilingual). This repository contains the pilot harness and measurements, not model weights or a copy of Laya's source.
