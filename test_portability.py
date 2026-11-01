"""Verify a relocated checkout can prepare a caller-selected vault."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_prepare_uses_explicit_vault_and_preserves_originals(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    shutil.copyfile(Path(__file__).with_name("pilot.py"), checkout / "pilot.py")
    vault = tmp_path / "vault"
    (vault / "notes").mkdir(parents=True)
    content = "---\ntitle: Example\n---\n\nOriginal source text.\n"
    for relative in ["AGENT_GUIDE.md", "README.md", "index.md", "notes/example.md"]:
        (vault / relative).write_text(content)
    command = [sys.executable, str(checkout / "pilot.py"), "prepare", "--vault", str(vault)]
    completed = subprocess.run(command, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    manifest = json.loads((checkout / "data/corpus-manifest.json").read_text())
    assert len(manifest) == 4
    assert (checkout / "data/corpus/notes/example.md").read_text() == content
    assert (vault / "notes/example.md").read_text() == content
    repeated = subprocess.run(command, capture_output=True, text=True)
    assert repeated.returncode != 0
    assert "Frozen corpus already exists" in repeated.stderr


def test_prepare_requires_explicit_source(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    shutil.copyfile(Path(__file__).with_name("pilot.py"), checkout / "pilot.py")
    completed = subprocess.run([sys.executable, str(checkout / "pilot.py"), "prepare"], capture_output=True, text=True)
    assert completed.returncode != 0
    assert "prepare requires --vault" in completed.stderr
    assert not (checkout / "data").exists()
