#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# Run one incremental idempotent Spark ingest for a month (YYYY-MM) on K8s.
# Usage: .\scripts\run-ingest.ps1 2024-01
#
# The month is read positionally ($args[0]) on purpose: a parametrised script
# with [Parameter(Mandatory)] proved unreliable on some PowerShell 5.1 hosts.
$Month = $args[0]
if (-not $Month) { throw "Usage: run-ingest.ps1 <YYYY-MM>" }
$Root = Split-Path $PSScriptRoot -Parent
# Pick up winget-installed tools without a shell restart.
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
$Chart = "$Root/infra/helm/spark-jobs"
# RBAC once (idempotent): ServiceAccount + Role + RoleBinding for the jobs.
helm template spark-rbac $Chart --set month=$Month --show-only templates/rbac.yaml | kubectl apply -f -
# (Re)create the month job. Deleting first makes the run repeatable: a
# completed Job is immutable, so re-applying requires a fresh object.
kubectl -n lakehouse delete job "spark-ingest-$Month" --ignore-not-found
helm template spark-jobs $Chart --set month=$Month | kubectl apply -f -
kubectl -n lakehouse wait --for=condition=complete --timeout=1800s "job/spark-ingest-$Month"
kubectl -n lakehouse logs "job/spark-ingest-$Month" --tail=30
