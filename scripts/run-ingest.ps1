#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# Run one incremental idempotent Spark ingest for a month (YYYY-MM) on K8s.
param([Parameter(Mandatory = $true)][string]$Month)
$Root = Split-Path $PSScriptRoot -Parent
$Chart = Join-Path $Root "infra" "helm" "spark-jobs"
# RBAC once (idempotent)
helm template spark-rbac $Chart --set month=$Month --show-only templates/rbac.yaml | kubectl apply -f -
# (Re)create the month job
kubectl -n lakehouse delete job "spark-ingest-$Month" --ignore-not-found
helm template spark-jobs $Chart --set month=$Month | kubectl apply -f -
kubectl -n lakehouse wait --for=condition=complete --timeout=1800s "job/spark-ingest-$Month"
kubectl -n lakehouse logs "job/spark-ingest-$Month" --tail=30
