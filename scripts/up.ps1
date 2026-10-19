#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# One-command rebuild from zero: cluster (Terraform) + data plane (Helm).
# Argo CD is installed for GitOps visibility; app sync from Git requires a
# remote (see docs/DECISIONS.md D10) - meanwhile this script applies the same
# charts Argo CD will sync, so the source of truth stays the repo.
# NOTE: plain "a/b" paths (forward slashes work on Windows PowerShell 5.1).
$Root = Split-Path $PSScriptRoot -Parent
# Pick up winget-installed tools without shell restart.
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# Small helper to print a readable step banner.
function Step([string]$msg) { Write-Host "`n=== $msg ===" }

# 1/7 - Infrastructure as code: create the local Kubernetes cluster (kind) and
# publish the NodePorts used by the host (MinIO 9000/9001, Trino 8080, Lakekeeper 8181).
Step "1/7 terraform: kind cluster"
Push-Location "$Root/infra/terraform"
try {
  terraform init        # download the kind provider
  terraform validate    # static syntax/consistency check
  terraform apply -auto-approve
} finally { Pop-Location }

# 2/7 - Register the Helm repositories once (no-op if already added).
Step "2/7 helm repos"
helm repo add argo https://argoproj.github.io/argo-helm 2>$null | Out-Null
helm repo add trino https://trinodb.github.io/charts 2>$null | Out-Null
helm repo update 2>$null | Out-Null

# 3/7 - Argo CD (GitOps UI/controller). Uses our values file for memory limits.
Step "3/7 argocd"
helm upgrade --install argocd argo/argo-cd --version 10.10.3 `
  -n argocd --create-namespace -f "$Root/infra/helm/argocd/values.yaml"
kubectl -n argocd wait --for=condition=available --timeout=420s deployment/argocd-server

# 4/7 - Storage + catalog: MinIO (S3), Postgres (catalog metadata only) and
# Lakekeeper (Iceberg REST catalog). Wait after each dependency level.
Step "4/7 storage + catalog (minio, postgres, lakekeeper)"
helm upgrade --install lakehouse-minio "$Root/infra/helm/minio" `
  -n lakehouse --create-namespace
helm upgrade --install lakehouse-postgres "$Root/infra/helm/postgres" `
  -n lakehouse
kubectl -n lakehouse wait --for=condition=ready --timeout=300s pod -l app=minio
kubectl -n lakehouse wait --for=condition=ready --timeout=300s pod -l app=postgres
helm upgrade --install lakehouse-lakekeeper "$Root/infra/helm/lakekeeper" `
  -n lakehouse
kubectl -n lakehouse wait --for=condition=ready --timeout=300s pod -l app=lakekeeper

# 5/7 - Trino (the SQL query engine). The official chart is vendored as a
# dependency; our values file pins the version and the coordinator/worker sizing.
Step "5/7 trino (official chart 1.44.0, app 483)"
helm dependency update "$Root/infra/helm/trino"
helm upgrade --install lakehouse-trino "$Root/infra/helm/trino" `
  -n lakehouse
kubectl -n lakehouse wait --for=condition=ready --timeout=600s pod -l app.kubernetes.io/instance=lakehouse-trino

# 6/7 - Build the Spark runner image (Spark + Iceberg/S3A jars + JRE 17) and
# load it into the kind node; then apply the Spark RBAC (ServiceAccount/Role).
Step "6/7 spark-runner image (build + kind load)"
docker build -f "$Root/docker/spark-runner.Dockerfile" `
  -t lakehouse/spark-runner:3.5.9-0.1.0 $Root
kind load docker-image lakehouse/spark-runner:3.5.9-0.1.0 --name lakehouse
helm template spark-rbac "$Root/infra/helm/spark-jobs" `
  --set month=bootstrap --show-only templates/rbac.yaml | kubectl apply -f -

# 7/7 - Wait for the catalog bootstrap Job, then create the namespace and the
# (empty) Iceberg table through the REST catalog with PyIceberg.
Step "7/7 catalog bootstrap (warehouse is automatic; namespace/table via REST)"
kubectl -n lakehouse wait --for=condition=complete --timeout=300s job/lakekeeper-bootstrap
$VenvPython = "$Root/.venv/Scripts/python.exe"
if (Test-Path $VenvPython) {
  & $VenvPython "$Root/scripts/lakekeeper-smoke.py"
} else {
  Write-Host "venv not found: create namespace/table with scripts/lakekeeper-smoke.py once .venv exists."
}

Write-Host "`nup: DONE. Next: scripts/upload-raw.py, then scripts/run-ingest.ps1 per month."
