"""Tests for scripts/verify-results.py (acceptance comparison)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-results.py"
REFERENCE = ROOT / "experiments"


def run_verifier(candidate: Path) -> subprocess.CompletedProcess[str]:
    """Run the verifier against a candidate directory."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(candidate), "--reference-dir", str(REFERENCE)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def make_candidate(tmp_path: Path) -> Path:
    """Copy the committed Trino results into a fresh candidate directory."""
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    for path in REFERENCE.glob("phase5_*.json"):
        shutil.copy2(path, candidate / path.name)
    return candidate


def test_committed_results_pass(tmp_path: Path) -> None:
    """The committed reference must satisfy every check."""
    result = run_verifier(make_candidate(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "all checks passed" in result.stdout


def test_tampered_rowcount_fails(tmp_path: Path) -> None:
    """A wrong total must fail with the rowcount label."""
    candidate = make_candidate(tmp_path)
    path = candidate / "phase5_01_rowcount.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["rows"][0][0] = "1"
    path.write_text(json.dumps(data), encoding="utf-8")
    result = run_verifier(candidate)
    assert result.returncode == 1
    assert "FAIL rowcount" in result.stdout


def test_tampered_query_result_fails(tmp_path: Path) -> None:
    """A changed deterministic query result must be detected."""
    candidate = make_candidate(tmp_path)
    path = candidate / "phase5_03_top_pickup_zones.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["rows"][0][0] = "999"
    path.write_text(json.dumps(data), encoding="utf-8")
    result = run_verifier(candidate)
    assert result.returncode == 1
    assert "FAIL 03_top_pickup_zones" in result.stdout
