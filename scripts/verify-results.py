"""Compare a fresh Trino run (candidate dir) with the committed reference results.

Used by ``scripts/verify.ps1``. Exits 0 when every check passes, 1 otherwise, so
it can gate a rebuild. Structural checks (rowcount, per-source counts, snapshot
totals) catch data regressions; exact row/column comparison on the deterministic
queries catches logic regressions.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

# Snapshot ids/timestamps change on every rebuild, so 04 is checked structurally
# (counts + operations) rather than byte-for-byte.
EXACT_STEMS = [
    "01_rowcount",
    "02_monthly_stats",
    "03_top_pickup_zones",
    "05_zone_names",
]


def load(path: Path) -> dict:
    """Load one JSON result file."""
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    """Run all checks; return a process exit code."""
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_dir", type=Path)
    parser.add_argument("--reference-dir", type=Path, default=Path("experiments"))
    args = parser.parse_args()

    failures: list[str] = []

    def check(ok: bool, label: str) -> None:
        """Record and print one PASS/FAIL line."""
        print(("PASS " if ok else "FAIL ") + label, flush=True)
        if not ok:
            failures.append(label)

    # Expected per-source counts come from the committed ingest summaries, so
    # the "truth" is the ingestion output, not a hard-coded number.
    expected: dict[str, int] = {}
    for path in sorted(args.reference_dir.glob("phase4_ingest_*.json")):
        data = load(path)
        expected[data["source_file"]] = int(data["valid_rows"])
    total = sum(expected.values())

    # --- Structural checks on the candidate run.
    rowcount = load(args.candidate_dir / "phase5_01_rowcount.json")
    got_total = int(rowcount["rows"][0][0])
    check(got_total == total, f"rowcount {got_total} == sum(valid_rows) {total}")

    monthly = load(args.candidate_dir / "phase5_02_monthly_stats.json")
    got_counts = {row[0]: int(row[1]) for row in monthly["rows"]}
    check(got_counts == expected, "per-source counts match ingest summaries")

    snapshots = load(args.candidate_dir / "phase5_04_snapshots.json")
    # The summary column is a Python dict rendered as text; literal_eval parses
    # it back without executing anything.
    summaries = [ast.literal_eval(row[3]) for row in snapshots["rows"]]
    operations = {row[2] for row in snapshots["rows"]}
    final_total = int(summaries[-1]["total-records"]) if summaries else -1
    check(len(summaries) >= len(expected) and "append" in operations, "snapshots per load")
    check(final_total == total, f"last snapshot total-records {final_total} == {total}")

    # --- Exact comparison on the deterministic queries.
    for stem in EXACT_STEMS:
        candidate = load(args.candidate_dir / f"phase5_{stem}.json")
        reference = load(args.reference_dir / f"phase5_{stem}.json")
        same = (
            candidate["columns"] == reference["columns"] and candidate["rows"] == reference["rows"]
        )
        check(same, f"{stem} identical to committed reference")

    if failures:
        print(f"\n{len(failures)} check(s) failed", flush=True)
        return 1
    print("\nall checks passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
