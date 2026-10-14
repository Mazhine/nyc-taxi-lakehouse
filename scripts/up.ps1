#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# One-command rebuild from zero: cluster (Terraform) + data plane (Helm).
# Argo CD is installed for GitOps visibility; app sync from Git requires a
# remote (see docs/DECISIONS.md D10) — meanwhile this script applies the same
# charts Argo CD will sync, so the source of truth stays the repo.
$Root = Split-Path $PSScriptRoot -Parent

function Step([string]$msg) { Write-Host "`n=== $msg ===" }

Step "1/5 terraform: kind cluster"
Push-Location (Join-Path $Root "infra" "terraform")
try {
  terraform init
  terraform validate
  terraform apply -auto-approve
} finally { Pop-Location }

Step "2/5 helm repos"
helm repo add argo https://argoproj.github.io/argo-helm 2>$null | Out-Null
helm repo update argo 2>$null | Out-Null

Step "3/5 argocd"
helm upgrade --install argocd argo/argo-cd --version 10.10.3 `
  -n argocd --create-namespace -f (Join-Path $Root "infra" "helm" "argocd" "values.yaml")
kubectl -n argocd wait --for=condition=available --timeout=420s deployment/argocd-server

Step "4/5 storage + catalog (minio, postgres, lakekeeper)"
helm upgrade --install lakehouse-minio (Join-Path $Root "infra" "helm" "minio") `
  -n lakehouse --create-namespace
helm upgrade --install lakehouse-postgres (Join-Path $Root "infra" "helm" "postgres") `
  -n lakehouse
kubectl -n lakehouse wait --for=condition=ready --timeout=300s pod -l app=minio
kubectl -n lakehouse wait --for=condition=ready --timeout=300s pod -l app=postgres
helm upgrade --install lakehouse-lakekeeper (Join-Path $Root "infra" "helm" "lakekeeper") `
  -n lakehouse
kubectl -n lakehouse wait --for=condition=ready --timeout=300s pod -l app=lakekeeper

Step "5/5 smoke"
kubectl -n lakehouse get pods
kubectl -n lakehouse logs job/minio-make-buckets --tail=5
kubectl -n lakehouse logs job/lakekeeper-bootstrap --tail=3
Write-Host "`nup: DONE. Trino + jobs land in later phases (scripts still no-op there)."
