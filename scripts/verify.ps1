#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# Post-rebuild acceptance check: stack up + data loaded.
# Re-runs sql/*.sql into a temp dir and compares with the committed results.
$Root = Split-Path $PSScriptRoot -Parent
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
$Python = "$Root/.venv/Scripts/python.exe"
if (-not (Test-Path $Python)) { throw "venv missing: run the setup in docs/RUNBOOK.md" }

Write-Host "`n=== 1/3 workloads ready ==="
kubectl -n lakehouse wait --for=condition=available --timeout=180s deployment -l app=minio
kubectl -n lakehouse wait --for=condition=available --timeout=180s deployment -l app=postgres
kubectl -n lakehouse wait --for=condition=available --timeout=180s deployment -l app=lakekeeper
kubectl -n lakehouse wait --for=condition=available --timeout=180s deployment -l app.kubernetes.io/instance=lakehouse-trino

Write-Host "`n=== 2/3 fresh Trino queries ==="
$Tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("lakehouse-verify-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $Tmp | Out-Null
try {
  & $Python "$Root/scripts/trino-query.py" --out-dir $Tmp
  if ($LASTEXITCODE -ne 0) { throw "trino-query.py failed" }

  Write-Host "`n=== 3/3 compare with committed results ==="
  & $Python "$Root/scripts/verify-results.py" $Tmp --reference-dir "$Root/experiments"
  if ($LASTEXITCODE -ne 0) { throw "verify-results.py failed" }
} finally {
  Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
}
Write-Host "`nverify: PASS" -ForegroundColor Green
