#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# Benchmarks need the stack up + data loaded (see docs/RUNBOOK.md).
# Delegates to scripts/bench-iceberg.py; outputs go to experiments/.
$Root = Split-Path $PSScriptRoot -Parent
$Python = "$Root/.venv/Scripts/python.exe"
if (-not (Test-Path $Python)) { throw "venv missing: run the setup in docs/RUNBOOK.md" }
& $Python "$Root/scripts/bench-iceberg.py"
# Propagate the Python exit code so callers can detect a failed benchmark.
exit $LASTEXITCODE
