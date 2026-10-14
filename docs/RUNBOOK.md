# RUNBOOK

## Prerequisites (Windows 11 + PowerShell)
- Docker Desktop running (WSL2 backend). Check: `docker info`.
- Tools: Python 3.12, kubectl, helm, terraform, kind (see README pins).
- `~/.wslconfig` limiting WSL2 to 20 GB (created in Phase 0).
- No heavy project running in parallel during benchmarks.

## Start (one command)
```powershell
.\scripts\up.ps1
```
Runs: Terraform `init/apply` (kind cluster) → Argo CD → MinIO → Postgres →
Lakekeeper → Trino → smoke checks.

## Stop
```powershell
.\scripts\down.ps1
```
Destroys the kind cluster via Terraform (`terraform destroy -auto-approve`).
MinIO data lives on a Docker volume and is deleted with the cluster (by design:
rebuild is from code + re-downloaded TLC files, never from git).

## Tests (no cluster needed)
```powershell
.\scripts\test.ps1
```
`ruff check`, `pytest`, `terraform validate/fmt -check`, `helm lint`, kubeconform.

## Benchmarks
```powershell
.\scripts\bench.ps1
```
Writes raw outputs to `experiments/` (JSON + logs). Medians computed over repeats.

## Data
```powershell
.\scripts\download-data.ps1
```
Downloads TLC parquet months + zone lookup into `data/` (git-ignored).

## Troubleshoot
| Symptom | Fix |
|---|---|
| `docker info` fails | Start Docker Desktop, wait ~60s, retry |
| kind cluster stuck | `kind delete cluster --name lakehouse`, rerun `up.ps1` |
| Terraform provider error | `terraform init -upgrade` in `infra/terraform` |
| MinIO login fails | Check `.env` (copy from `.env.example`), port-forward 9000/9001 |
| Trino no rows | Check Lakekeeper warehouse + Spark job logs |
| OOM in WSL2 | Lower Trino/Spark limits, close other apps, check `.wslconfig` |
