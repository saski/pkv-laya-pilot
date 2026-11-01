"""Render measured results without loading models or accessing the source vault."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def render(data: dict[str, Any]) -> str:
    summary = data["summary"]
    arms = summary["arms"]
    reference_tokens = arms["lexical"]["5"]["context_tokens_total"]
    lines = [
        "# Retrieval evaluation results", "",
        f"Queries: {summary['query_count']}; answerable cases: {summary['answerable_queries']}.", "",
        "Quality excludes no-answer controls. Context and latency include all queries. Context tokens are downstream snippet counts, not paid API billing or total reranker work.", "",
        "| Method | Source recall | nDCG | Mean context tokens | Context reduction vs lexical top 5 |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm, k in [("lexical", "5"), ("laya", "5"), ("lexical", "3"), ("laya", "3")]:
        metric = arms[arm][k]
        reduction = 1 - metric["context_tokens_total"] / reference_tokens
        lines.append(f"| {arm} top {k} | {metric['recall']:.1%} | {metric['ndcg']:.3f} | {metric['context_tokens_mean']:.0f} | {reduction:.1%} |")
    lines.extend(["", "| Method | Median resident latency | p95 resident latency |", "|---|---:|---:|"])
    for arm in ["lexical", "laya"]:
        lines.append(f"| {arm} | {arms[arm]['latency_median_ms']:.1f} ms | {arms[arm]['latency_p95_ms']:.1f} ms |")
    lines.extend(["", f"Model-input truncations: {data['truncated_predictions']}; unknown truncation records: {data['unknown_truncation_records']}.",
                  f"Laya input tokens in the first round: {summary['reranker_input_tokens_total_first_repetition']:,} (different tokenizer from downstream context).", "",
                  "This report summarizes measurements only. Review the protocol, per-query errors, source changes and uncertainty before making an adoption decision.", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    text = render(json.loads(args.result.read_text()))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
