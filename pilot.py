"""Reproducible, local-only lexical retrieval and Laya reranking experiment."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import resource
import statistics
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SCHEMA = {"relevant": {"type": "noul", "instructions": "Does the passage contain information that directly helps answer the query?"}}
STOP = set("a an and are as at be by can could did do does for from how i in is it its me my of on or our that the their these this to was we what when where which why with would you your de del el la las los un una unos unas y o en por para que como cual cuales cuando donde con al se es son ser hay mi mis tu tus su sus lo nos este esta estos estas sobre puede podria quiero necesito puedes tenemos tengo hacer dame".split())


def normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKD", value.lower()).encode("ascii", "ignore").decode()))


def words(value: str) -> set[str]:
    return {word for word in normalize(value).split() if word not in STOP and len(word) > 1}


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def metrics(ranking: list[str], gold: dict[str, int], k: int) -> dict[str, float]:
    relevant = {path for path, grade in gold.items() if grade > 0}
    if not relevant:
        raise ValueError("Recall is undefined for unanswerable queries; report them separately")
    selected = ranking[:k]
    hits = set(selected) & relevant
    reciprocal = next((1 / (i + 1) for i, path in enumerate(selected) if path in relevant), 0.0)
    dcg = sum((2 ** gold.get(path, 0) - 1) / math.log2(i + 2) for i, path in enumerate(selected))
    ideal = sum((2 ** grade - 1) / math.log2(i + 2) for i, grade in enumerate(sorted(gold.values(), reverse=True)[:k]))
    direct_hit = any(gold.get(path, 0) >= 2 for path in selected)
    return {"recall": len(hits) / len(relevant), "hit": float(bool(hits)), "direct_hit": float(direct_hit), "reciprocal_rank": reciprocal, "ndcg": dcg / ideal if ideal else 0.0}


def rank_by_relevance(probabilities: list[float]) -> list[int]:
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities):
        raise ValueError("Model probability must be finite and in [0, 1]")
    return sorted(range(len(probabilities)), key=lambda i: (-probabilities[i], i))


@dataclass(frozen=True)
class Document:
    path: str
    title: str
    summary: str
    aliases: str
    tags: str
    body: str
    body_start: int


class Retriever:
    """Fixed lexical approximation of the existing metadata/section-first procedure."""

    def __init__(self, corpus_dir: Path) -> None:
        import tiktoken
        import yaml

        self.encoder = tiktoken.get_encoding("o200k_base")
        self.docs: list[Document] = []
        for path in sorted(corpus_dir.rglob("*.md")):
            text = path.read_text()
            match = re.match(r"\A---\n(.*?)\n---\n", text, flags=re.S)
            meta = yaml.safe_load(match.group(1)) or {} if match else {}
            body = text[match.end():] if match else text
            self.docs.append(Document(
                path=str(path.relative_to(corpus_dir)), title=str(meta.get("title", path.stem)),
                summary=str(meta.get("summary", "")), aliases=str(meta.get("aliases", "")),
                tags=str(meta.get("tags", "")), body=body,
                body_start=text[:match.end()].count("\n") + 1 if match else 1,
            ))
        self.features: dict[str, tuple[set[str], set[str], set[str], set[str]]] = {
            d.path: (words(d.title + " " + d.aliases), words(d.tags), words(d.summary), words(d.body)) for d in self.docs
        }
        frequencies: Counter[str] = Counter()
        for fields in self.features.values():
            frequencies.update(set.union(*fields))
        self.idf = {term: math.log(1 + len(self.docs) / (1 + count)) for term, count in frequencies.items()}

    def find(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        terms = words(query["query"] + " " + " ".join(query.get("search_terms", [])))
        query_normalized = normalize(query["query"])
        scored: list[tuple[float, float, Document]] = []
        for doc in self.docs:
            title, tags, summary, body = self.features[doc.path]
            overlaps = [sum(self.idf.get(t, 1.0) for t in terms & field) for field in (title, tags, summary, body)]
            normalized_title = normalize(doc.title)
            exact = float(len(normalized_title.split()) >= 2 and normalized_title in query_normalized)
            meta_score = 100 * exact + 8 * overlaps[0] + 4 * overlaps[1] + 2 * overlaps[2]
            # Metadata matches are considered before body-only fallback matches.
            if meta_score or overlaps[3]:
                scored.append((meta_score, overlaps[3], doc))
        scored.sort(key=lambda row: (-row[0], -row[1], row[2].path))
        return [self.passage(doc, terms, meta_score, body_score) for meta_score, body_score, doc in scored[:10]]

    def passage(self, doc: Document, terms: set[str], meta_score: float, body_score: float) -> dict[str, Any]:
        lines = doc.body.splitlines()
        windows = [(i, lines[i:i + 22]) for i in range(0, max(1, len(lines)), 10)]
        scored = [(sum(self.idf.get(term, 1.0) for term in terms & words("\n".join(chunk))), i, chunk) for i, chunk in windows]
        _, offset, best = max(scored, key=lambda row: (row[0], -row[1]))
        source = f"Source: {doc.path}:{doc.body_start + offset}\nTitle: {doc.title}\nSummary: {doc.summary}\nPassage:\n" + "\n".join(best)
        encoded = self.encoder.encode(source)
        clipped = len(encoded) > 450
        if clipped:
            source = self.encoder.decode(encoded[:450]) + "\n[excerpt ends]"
        return {"path": doc.path, "line_start": doc.body_start + offset,
                "line_end_window": doc.body_start + offset + len(best) - 1,
                "text": source, "excerpt_clipped": clipped,
                "metadata_score": meta_score, "body_score": body_score}

    def context_tokens(self, candidates: list[dict[str, Any]], k: int) -> int:
        return len(self.encoder.encode("\n\n---\n\n".join(c["text"] for c in candidates[:k])))


def prepare(args: argparse.Namespace) -> None:
    if not args.vault:
        raise ValueError("prepare requires --vault /path/to/personal-knowledge-vault/vault")
    vault = Path(args.vault).expanduser().resolve(strict=True)
    if not (vault / "notes").is_dir() or not (vault / "AGENT_GUIDE.md").is_file():
        raise ValueError("The selected directory is not a PKV content root")
    corpus_dir = ROOT / "data/corpus"
    if corpus_dir.exists():
        raise FileExistsError("Frozen corpus already exists; do not overwrite an evaluated snapshot")
    paths: list[Path] = []
    for folder in ["notes", "maps", "projects", "portfolio", "_meta"]:
        paths.extend(sorted((vault / folder).rglob("*.md")))
    paths.extend(vault / p for p in ["AGENT_GUIDE.md", "README.md", "index.md"])
    manifest = []
    for path in sorted(set(paths)):
        relative = path.relative_to(vault)
        data = path.read_bytes()
        target = corpus_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest.append({"path": str(relative), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    write_json(ROOT / "data/corpus-manifest.json", manifest)
    print(json.dumps({"documents": len(manifest), "bytes": sum(x["bytes"] for x in manifest)}))


def candidates(args: argparse.Namespace) -> None:
    queries = json.loads((ROOT / "data/queries.json").read_text())
    start = time.perf_counter()
    retriever = Retriever(ROOT / "data/corpus")
    index_ms = (time.perf_counter() - start) * 1000
    rows = [{"id": q["id"], "query": q["query"], "candidates": retriever.find(q)} for q in queries]
    write_json(ROOT / "data/candidate-pool.json", {"index_load_ms": index_ms, "rows": rows})
    print(json.dumps({"queries": len(rows), "documents": len(retriever.docs), "index_load_ms": index_ms}))


def bootstrap_interval(values: list[float], rng: Any) -> list[float]:
    import numpy as np

    samples = rng.choice(np.array(values), size=(10000, len(values)), replace=True).mean(axis=1)
    return [float(v) for v in np.quantile(samples, [0.025, 0.975])]


def evaluate(args: argparse.Namespace) -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    import numpy as np
    import torch
    from laya import Agent

    queries = json.loads((ROOT / "data/queries.json").read_text())
    if len(queries) != 20:
        raise ValueError("This protocol requires exactly 20 frozen queries")
    setup = json.loads((ROOT / "results/bootstrap.json").read_text())
    for item in json.loads((ROOT / "data/corpus-manifest.json").read_text()):
        if digest_file(ROOT / "data/corpus" / item["path"]) != item["sha256"]:
            raise ValueError("Frozen corpus was changed")
    fingerprint = {name: digest_file(ROOT / name) for name in ["data/queries.json", "data/corpus-manifest.json", "PROTOCOL.md", "uv.lock", "pilot.py"]}
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.run_name):
        raise ValueError("Run name must contain only letters, digits, underscore or hyphen")
    output = ROOT / f"results/{args.run_name}.json"
    if output.exists():
        raise FileExistsError("Do not overwrite the first evaluation; preserve its evidence")
    start = time.perf_counter()
    retriever = Retriever(ROOT / "data/corpus")
    index_ms = (time.perf_counter() - start) * 1000
    start = time.perf_counter()
    agent = Agent(setup["model_path"], device="mps", expected_sha256={"model.safetensors": setup["weights_sha256"]})
    torch.mps.synchronize()
    model_load_ms = (time.perf_counter() - start) * 1000
    # Unrelated installation fixtures warm the device; evaluation labels are never used here.
    warm_states = [{"query": "How can I undo a Git commit?", "passage": "git reset --soft HEAD~1 keeps changes staged."}] * 10
    for _ in range(3):
        agent.predict_batch(warm_states, SCHEMA, batch_size=4, max_len=1024)
        torch.mps.synchronize()
    rng = random.Random(20261101)
    observations: list[dict[str, Any]] = []
    for repetition in range(5):
        ordered = list(queries)
        rng.shuffle(ordered)
        for q in ordered:
            arms = ["lexical", "laya"]
            rng.shuffle(arms)
            record: dict[str, Any] = {"id": q["id"], "repetition": repetition, "arm_order": arms}
            for arm in arms:
                torch.mps.synchronize()
                start = time.perf_counter()
                found = retriever.find(q)
                retrieval_ms = (time.perf_counter() - start) * 1000
                predictions: list[dict[str, Any]] = []
                probabilities: list[float] = []
                if arm == "laya" and found:
                    states = [{"query": q["query"], "passage": c["text"]} for c in found]
                    predictions = agent.predict_batch(states, SCHEMA, batch_size=4, max_len=1024)
                    torch.mps.synchronize()
                    probabilities = [float(p["answers"]["relevant"]["noul"]) for p in predictions]
                    selected = [found[i] for i in rank_by_relevance(probabilities)]
                else:
                    selected = found
                counts = {str(k): retriever.context_tokens(selected, k) for k in [3, 5, 10]}
                total_ms = (time.perf_counter() - start) * 1000
                record[arm] = {"ranking": [c["path"] for c in selected], "context_tokens": counts,
                               "retrieval_ms": retrieval_ms, "total_ms": total_ms,
                               "candidate_paths": [c["path"] for c in found], "probabilities": probabilities,
                               "usage": [p.get("usage", {}) for p in predictions]}
            observations.append(record)
            if record["lexical"]["candidate_paths"] != record["laya"]["candidate_paths"]:
                raise RuntimeError("The arms did not receive identical candidates")
            print(json.dumps({"repetition": repetition + 1, "id": q["id"], "lexical_ms": round(record["lexical"]["total_ms"], 2), "laya_ms": round(record["laya"]["total_ms"], 2)}), flush=True)
            write_json(ROOT / f"results/{args.run_name}-progress.json", {"fingerprint": fingerprint, "observations": observations})
    first = {row["id"]: row for row in observations if row["repetition"] == 0}
    query_results = []
    for q in queries:
        row = first[q["id"]]
        gold = q["relevance"]
        result: dict[str, Any] = {"id": q["id"], "query": q["query"], "kind": q["kind"], "answerable": bool(gold), "arms": {}}
        result["candidate_recall_at_10"] = metrics(row["lexical"]["candidate_paths"], gold, 10)["recall"] if gold else None
        for arm in ["lexical", "laya"]:
            rankings = [o[arm]["ranking"] for o in observations if o["id"] == q["id"]]
            result["arms"][arm] = {"ranking": row[arm]["ranking"], "context_tokens": row[arm]["context_tokens"],
                                  "stable_ranking": all(r == rankings[0] for r in rankings),
                                  "passage_direct_hit": {str(k): int(any(q.get("passage_relevance", {}).get(p, 0) >= 2 for p in row[arm]["ranking"][:k])) for k in [3, 5, 10]},
                                  "metrics": {str(k): metrics(row[arm]["ranking"], gold, k) for k in [3, 5, 10]} if gold else {}}
        query_results.append(result)
    summary: dict[str, Any] = {"query_count": len(queries), "answerable_queries": sum(bool(q["relevance"]) for q in queries), "arms": {}, "paired_differences": {}}
    bootstrap_rng = np.random.default_rng(20261101)
    for arm in ["lexical", "laya"]:
        latencies = [r[arm]["total_ms"] for r in observations]
        summary["arms"][arm] = {"latency_median_ms": statistics.median(latencies), "latency_p95_ms": float(np.quantile(latencies, 0.95)), "unstable_queries": sum(not r["arms"][arm]["stable_ranking"] for r in query_results)}
        for k in [3, 5, 10]:
            answerable = [r["arms"][arm]["metrics"][str(k)] for r in query_results if r["answerable"]]
            summary["arms"][arm][str(k)] = {key: statistics.mean(r[key] for r in answerable) for key in ["recall", "hit", "direct_hit", "reciprocal_rank", "ndcg"]}
            summary["arms"][arm][str(k)]["context_tokens_total"] = sum(r["arms"][arm]["context_tokens"][str(k)] for r in query_results)
            summary["arms"][arm][str(k)]["context_tokens_mean"] = statistics.mean(r["arms"][arm]["context_tokens"][str(k)] for r in query_results)
            summary["arms"][arm][str(k)]["passage_direct_hit"] = statistics.mean(r["arms"][arm]["passage_direct_hit"][str(k)] for r in query_results if r["answerable"])
    summary["candidate_recall_at_10"] = statistics.mean(r["candidate_recall_at_10"] for r in query_results if r["answerable"])
    summary["slices"] = {}
    for kind in ["historical_adaptation", "new_practical_query"]:
        selected_rows = [r for r in query_results if r["kind"] == kind and r["answerable"]]
        summary["slices"][kind] = {"answerable_queries": len(selected_rows), "arms": {}}
        for arm in ["lexical", "laya"]:
            summary["slices"][kind]["arms"][arm] = {
                str(k): {key: statistics.mean(r["arms"][arm]["metrics"][str(k)][key] for r in selected_rows)
                         for key in ["recall", "hit", "direct_hit", "ndcg"]} for k in [3, 5]
            } if selected_rows else {}
    for k in [3, 5]:
        for key in ["recall", "hit", "direct_hit", "ndcg"]:
            differences = [r["arms"]["laya"]["metrics"][str(k)][key] - r["arms"]["lexical"]["metrics"][str(k)][key] for r in query_results if r["answerable"]]
            summary["paired_differences"][f"{key}@{k}"] = {"mean": statistics.mean(differences), "bootstrap_95_ci": bootstrap_interval(differences, bootstrap_rng)}
    usages = [u for o in observations for u in o["laya"]["usage"]]
    unknown_usage = sum("truncated" not in u or "state_tokens_dropped" not in u for u in usages)
    truncated = [u for u in usages if u.get("truncated") or u.get("state_tokens_dropped", 0)]
    summary["reranker_input_tokens_total_first_repetition"] = sum(u.get("input_tokens", 0) for o in observations if o["repetition"] == 0 for u in o["laya"]["usage"])
    summary["unknown_truncation_records"] = unknown_usage
    summary["unanswerable_cases"] = [
        {"id": q["id"], "query": q["query"], "candidate_count": len(first[q["id"]]["lexical"]["ranking"]),
         "laya_max_relevance_probability": max(first[q["id"]]["laya"]["probabilities"], default=None),
         "note": "No abstention threshold tested; ranking is not a reliable answer."}
        for q in queries if not q["relevance"]
    ]
    result = {"fingerprint": fingerprint, "schema": SCHEMA, "setup": setup, "index_load_ms": index_ms,
              "model_load_ms": model_load_ms, "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "mps_driver_allocated_bytes": torch.mps.driver_allocated_memory(),
              "truncated_predictions": len(truncated), "unknown_truncation_records": unknown_usage, "summary": summary,
              "query_results": query_results, "observations": observations}
    write_json(output, result)
    print(json.dumps({"event": "complete", "summary": summary, "truncated_predictions": len(truncated)}, ensure_ascii=False), flush=True)


def main() -> None:
    os.environ["TIKTOKEN_CACHE_DIR"] = str(ROOT / ".cache/tiktoken")
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "candidates", "evaluate"])
    parser.add_argument("--run-name", default="evaluation")
    parser.add_argument("--vault", type=Path, help="PKV content root; required by prepare")
    args = parser.parse_args()
    {"prepare": prepare, "candidates": candidates, "evaluate": evaluate}[args.action](args)


if __name__ == "__main__":
    main()
