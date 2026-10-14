#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# Fast checks, no cluster needed (mirrors .github/workflows/ci.yml).
$Root = Split-Path $PSScriptRoot -Parent
# Pick up winget-installed tools (helm/terraform/kind) without shell restart.
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
$VenvBin = Join-Path (Join-Path $Root ".venv") "Scripts"
$VenvPython = Join-Path $VenvBin "python.exe"
if (Test-Path $VenvPython) {
  $Python = $VenvPython
  $Ruff = Join-Path $VenvBin "ruff.exe"
} else {
  $Python = "python"
  $Ruff = "ruff"
}
Push-Location $Root
try {
  & $Ruff check src tests scripts
  & $Ruff format --check src tests scripts
  & $Python -m pytest -q
  terraform -chdir=infra/terraform init -backend=false
  terraform -chdir=infra/terraform validate
  terraform -chdir=infra/terraform fmt -check
  helm dependency update infra/helm/trino
  foreach ($chart in @("minio", "postgres", "lakekeeper", "spark-jobs", "trino")) {
    helm lint "infra/helm/$chart"
  }
  # argocd has no local chart (upstream chart + our values file): render check.
  helm repo add argo https://argoproj.github.io/argo-helm 2>$null | Out-Null
  helm template argocd argo/argo-cd --version 10.10.3 -n argocd `
    -f infra/helm/argocd/values.yaml | Out-Null
  helm template lakehouse-minio infra/helm/minio | Out-Null
  helm template lakehouse-postgres infra/helm/postgres | Out-Null
  helm template lakehouse-lakekeeper infra/helm/lakekeeper | Out-Null
  helm template spark-jobs infra/helm/spark-jobs --set month=2024-01 | Out-Null
  helm template lakehouse-trino infra/helm/trino | Out-Null
  Write-Host "test: ALL GREEN (kubeconform runs in CI)"
} finally { Pop-Location }
