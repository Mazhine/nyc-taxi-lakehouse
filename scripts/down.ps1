#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# Tear everything down: Terraform destroys the kind cluster (and with it every
# Kubernetes object, including MinIO/Postgres data - nothing here is precious).
$Root = Split-Path $PSScriptRoot -Parent
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
Push-Location (Join-Path $Root "infra\terraform")
try { terraform destroy -auto-approve } finally { Pop-Location }
