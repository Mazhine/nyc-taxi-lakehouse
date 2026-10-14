#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# One-command rebuild from zero: cluster (Terraform) + data plane (Helm).
# Argo CD is installed for GitOps visibility; app sync from Git requires a
# remote (see docs/DECISIONS.md D10) — meanwhile this script applies the same
# charts Argo CD will sync, so the source of truth stays the repo.
$Root = Split-Path $PSScriptRoot -Parent
# Pick up winget-installed tools without shell restart.
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

function Step([string]$msg) { Write-Host "`n=== $msg ===" }

Step "1/7 terraform: kind cluster"
Push-Location (Join-Path $Root "infra" "terraform")
try {
  terraform init
  terraform validate
  terraform apply -auto-approve
} finally { Pop-Location }

Step "2/7 helm repos"
helm repo add argo https://argoproj.github.io/argo-helm 2>$null | Out-Null
helm repo add trino https://trinodb.github.io/charts 2>$null | Out-Null
helm repo update 2>$null | Out-Null

Step "3/7 argocd"
helm upgrade --install argocd argo/argo-cd --version 10.10.3 `
  -n argocd --create-namespace -f (Join-Path $Root "infra" "helm" "argocd" "values.yaml")
kubectl -n argocd wait --for=condition=available --timeout=420s deployment/argocd-server

Step "4/7 storage + catalog (minio, postgres, lakekeeper)"
helm upgrade --install lakehouse-minio (Join-Path $Root "infra" "helm" "minio") `
  -n lakehouse --create-namespace
helm upgrade --install lakehouse-postgres (Join-Path $Root "infra" "helm" "postgres") `
  -n lakehouse
kubectl -n lakehouse wait --for=condition=ready --timeout=300s pod -l app=minio
kubectl -n lakehouse wait --for=condition=ready --timeout=300s pod -l app=postgres
helm upgrade --install lakehouse-lakekeeper (Join-Path $Root "infra" "helm" "lakekeeper") `
  -n lakehouse
kubectl -n lakehouse wait --for=condition=ready --timeout=300s pod -l app=lakekeeper

Step "5/7 trino (official chart 1.44.0, app 483)"
helm dependency update (Join-Path $Root "infra" "helm" "trino")
helm upgrade --install lakehouse-trino (Join-Path $Root "infra" "helm" "trino") `
  -n lakehouse
kubectl -n lakehouse wait --for=condition=ready --timeout=600s pod -l app.kubernetes.io/instance=lakehouse-trino

Step "6/7 spark-runner image (build + kind load)"
docker build -f (Join-Path $Root "docker" "spark-runner.Dockerfile") `
  -t lakehouse/spark-runner:3.5.9-0.1.0 $Root
kind load docker-image lakehouse/spark-runner:3.5.9-0.1.0 --name lakehouse
helm template spark-rbac (Join-Path $Root "infra" "helm" "spark-jobs") `
  --set month=bootstrap --show-only templates/rbac.yaml | kubectl apply -f -

Step "7/7 catalog bootstrap (warehouse is automatic; namespace/table via REST)"
kubectl -n lakehouse wait --for=condition=complete --timeout=300s job/lakekeeper-bootstrap
$VenvPython = Join-Path (Join-Path (Join-Path $Root ".venv") "Scripts") "python.exe"
if (Test-Path $VenvPython) {
  & $VenvPython (Join-Path $Root "scripts" "lakekeeper-smoke.py")
} else {
  Write-Host "venv not found: create namespace/table with scripts/lakekeeper-smoke.py once .venv exists."
}

Write-Host "`nup: DONE. Next: scripts/upload-raw.py, then scripts/run-ingest.ps1 per month."
