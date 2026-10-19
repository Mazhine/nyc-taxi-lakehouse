# Contributing

Thanks for looking at this project. It is a self-contained, single-node
lakehouse meant to be **reproducible and honest**: every published number must
be traceable to a real run in `experiments/`.

## Getting set up

1. Install the prerequisites from the README (Docker Desktop, kubectl, Helm,
   Terraform, kind, Python 3.12, PowerShell 5.1).
2. Download the data: `.\scripts\download-data.ps1`
3. Bring the platform up: `.\scripts\up.ps1` (7 steps)
4. Run the fast checks without a cluster: `.\scripts\test.ps1`

## What CI runs

`.github/workflows/ci.yml` runs `ruff check` + `ruff format --check`, `pytest`,
`terraform fmt/validate`, `helm lint` (+ template render) and `kubeconform` on
the rendered manifests. Spark-dependent tests run inside `apache/spark:3.5.9`
(CI has no Kubernetes cluster).

## Ground rules

- **Measure, don't guess.** Add benchmarks as JSON under `experiments/` and
  reference the file in the README table. If something is not measured, say so
  explicitly (mark it `TBD` / "not tested").
- **Record decisions.** Any non-obvious choice (a tool swap, a workaround, a
  limit) gets an entry in `docs/DECISIONS.md` with the reasoning and evidence.
- **Contracts are the source of truth.** Column names, types and quality rules
  live in `contracts/*.yaml`; change the contract first, then the code.
- **Idempotency matters.** Ingestion must be safe to re-run: replays should
  report `skipped_already_loaded` and add zero files.
- **Style.** Python is formatted with `ruff format` (line length in
  `pyproject.toml`); comments/docstrings in English. PowerShell scripts target
  Windows PowerShell 5.1 (avoid multi-argument `Join-Path`, prefer `"$Root/a/b"`).

## Pull request checklist

- [ ] `.\scripts\test.ps1` is green (or the CI commands pass locally).
- [ ] New behavior is covered by a test in `tests/`.
- [ ] Any new number in the README points to an `experiments/` artifact.
- [ ] `docs/DECISIONS.md` updated if a design decision changed.
