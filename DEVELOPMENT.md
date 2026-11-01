# Development and resumption

The archived evidence can be read without installing anything. The commands below intentionally recreate the environment and download the model when the experiment is resumed.

## Lightweight verification

Use Python 3.11 and `uv`. To run metric and portability tests without installing Laya or PyTorch:

```bash
uv sync --frozen --only-group dev
uv run --frozen --only-group dev pytest -q -p no:cacheprovider
```

The tests use temporary toy documents and do not download a model or read a personal vault.

## Recreate the local experiment

On an Apple Silicon Mac with MPS support:

```bash
uv sync --frozen
uv run python bootstrap.py
uv run python pilot.py prepare --vault /path/to/personal-knowledge-vault/vault
cp datasets/pkv-2026-11-01/queries.json data/queries.json
uv run python pilot.py candidates
```

`bootstrap.py` downloads the pinned public multilingual checkpoint into `.cache/huggingface`, verifies that it loads on MPS, and runs an unrelated smoke test. It also prepares the context tokenizer cache. It does not inspect the PKV. No paid model API or API key is required for these public downloads.

`prepare` creates an ignored local snapshot of the curated vault and records its hashes. It requires the content root containing `AGENT_GUIDE.md`, `README.md`, `index.md` and `notes/`. It refuses to overwrite an existing corpus snapshot. `candidates` writes local passages for reviewing the baseline and labels before model scoring.

The copied query file is a starting point, not fresh ground truth. Compare the new manifest with `datasets/pkv-2026-11-01/corpus-manifest.json`; inspect changed notes and re-review source and passage relevance. Do not tune a new prompt on the old evaluation set and claim independent validation.

Once the dataset, labels and protocol are fixed:

```bash
uv run python pilot.py evaluate --run-name revisit-01
uv run python report.py results/revisit-01.json --output results/revisit-01.md
```

Use a new run name for every completed run. The evaluator never overwrites a completed result. It runs five paired rounds, uses the local checkpoint with offline inference settings, separates startup costs from resident query latency, and verifies corpus hashes.

## Files

- `pilot.py`: lexical candidates, identical excerpt construction, Laya reranking, paired timings and metrics.
- `bootstrap.py`: explicit model download and local installation smoke test.
- `report.py`: standard-library report generation from a completed JSON run; no model loading.
- `test_metrics.py`, `test_portability.py`: behavior checks for scoring and portable local setup.
- `uv.lock`: exact dependency versions from the experiment.
- `PROTOCOL.md`: method and acceptance criteria fixed before original model scoring.
- `archive/2026-11-01/`: measured results and decision, with local cache paths removed.
- `datasets/pkv-2026-11-01/`: sanitized query labels and corpus hashes; no source body text.

The portable publication parameterizes the old absolute source path and resolves its checkout root dynamically. Ranking, snippet construction and measurement logic are unchanged. Archived fingerprints refer to the original local files, not to these portable versions. Original conversation provenance and human-readable review transcripts were intentionally not uploaded.

Runtime files under `.venv/`, `.cache/`, `data/` and `results/` are ignored. Inspect an explicit staged file list before publishing future results; those files can contain private source passages. No workflow automatically installs dependencies or downloads models on GitHub.
