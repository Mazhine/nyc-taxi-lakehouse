#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# Fast checks, no cluster needed.
$Root = Split-Path $PSScriptRoot -Parent
Push-Location $Root
try {
  ruff check src tests
  pytest -q
  terraform -chdir=infra/terraform init -backend=false
  terraform -chdir=infra/terraform validate
  terraform -chdir=infra/terraform fmt -check
} finally { Pop-Location }
