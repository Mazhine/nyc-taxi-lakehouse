#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# Tear everything down.
$Root = Split-Path $PSScriptRoot -Parent
Push-Location (Join-Path $Root "infra" "terraform")
try { terraform destroy -auto-approve } finally { Pop-Location }
