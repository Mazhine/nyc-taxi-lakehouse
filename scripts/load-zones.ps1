#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# Load the taxi zone reference table (265 rows) from raw/taxi_zone_lookup.csv.
# Run once after upload-raw.py; idempotent (table exists -> skip).
$Root = Split-Path $PSScriptRoot -Parent
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
$Chart = "$Root/infra/helm/spark-jobs"
# Recreate the Job (deleting first makes the run repeatable) and apply only the
# zones template, then wait for completion and show the last log lines.
kubectl -n lakehouse delete job spark-zones --ignore-not-found | Out-Null
helm template spark-zones $Chart --show-only templates/job-zones.yaml | kubectl apply -f -
kubectl -n lakehouse wait --for=condition=complete --timeout=900s job/spark-zones
kubectl -n lakehouse logs job/spark-zones --tail=20
