"""Download the pinned public checkpoint and verify local inference."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ["HF_HOME"] = str(ROOT / ".cache/huggingface")
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["TIKTOKEN_CACHE_DIR"] = str(ROOT / ".cache/tiktoken")
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    import tiktoken
    import torch
    from huggingface_hub import snapshot_download
    from laya import PINNED_REVISIONS, Agent

    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable; do not silently change benchmark device")
    repo = "convaiinnovations/laya-multilingual"
    revision = PINNED_REVISIONS[repo]
    start = time.perf_counter()
    model_path = Path(snapshot_download(
        repo, revision=revision, token=False,
        allow_patterns=["model.safetensors", "rl_agent_config.json", "tokenizer/*", "encoder/*"],
    ))
    download_s = time.perf_counter() - start
    print(json.dumps({"event": "download_complete", "seconds": download_s, "revision": revision}), flush=True)
    weights_sha = sha256(model_path / "model.safetensors")
    start = time.perf_counter()
    agent = Agent(str(model_path), device="mps", expected_sha256={"model.safetensors": weights_sha})
    torch.mps.synchronize()
    load_s = time.perf_counter() - start
    questions = {"relevant": {"type": "noul", "instructions": "Does the passage contain information that directly helps answer the query?"}}
    states = [
        {"query": "How can I undo a Git commit while preserving the changes?", "passage": "git reset --soft HEAD~1 removes the last commit while keeping its changes staged."},
        {"query": "How can I undo a Git commit while preserving the changes?", "passage": "A blue whale is a marine mammal."},
    ]
    start = time.perf_counter()
    predictions = agent.predict_batch(states, questions, batch_size=2, max_len=1024)
    torch.mps.synchronize()
    inference_s = time.perf_counter() - start
    tiktoken.get_encoding("o200k_base").encode("Tokenizer installation smoke test")
    result = {
        "python": platform.python_version(), "platform": platform.platform(),
        "packages": {name: importlib.metadata.version(name) for name in ["laya", "torch", "transformers", "huggingface-hub", "tiktoken"]},
        "device": "mps", "model_repo": repo, "model_revision": revision,
        "model_path": str(model_path), "weights_sha256": weights_sha,
        "weights_bytes": (model_path / "model.safetensors").stat().st_size,
        "download_seconds": download_s, "cold_model_load_seconds": load_s,
        "first_prediction_seconds": inference_s, "smoke_predictions": predictions,
    }
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results/bootstrap.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, default=str), flush=True)


if __name__ == "__main__":
    main()
