#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# One-command rebuild: terraform apply (kind) + Argo CD sync + smoke checks.
$Root = Split-Path $PSScriptRoot -Parent
Push-Location (Join-Path $Root "infra" "terraform")
try {
  terraform init
  terraform validate
  terraform apply -auto-approve
} finally { Pop-Location }
Write-Host "up: cluster applied. Argo CD sync + app manifests land in Phase 2/3."
