#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# Download NYC TLC yellow-taxi parquet months + zone lookup into data/ (git-ignored).
$Base = "https://d37ci6vzurychx.cloudfront.net/trip-data"
$ZoneUrl = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
$DataDir = Join-Path (Join-Path $PSScriptRoot "..") "data"
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
# 6 months ingested by the pipeline + 2 older months used to inspect schema drift.
$Months = @("2019-01", "2023-01", "2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06")
foreach ($m in $Months) {
  $file = "yellow_tripdata_$m.parquet"
  $dest = Join-Path $DataDir $file
  # Skip files already downloaded (resume-friendly).
  if (Test-Path $dest) { Write-Host "exists: $file"; continue }
  Write-Host "downloading $file ..."
  Invoke-WebRequest -Uri "$Base/$file" -OutFile $dest
}
# Reference/dimension CSV for the nyc.taxi_zones table.
$zoneDest = Join-Path $DataDir "taxi_zone_lookup.csv"
if (-not (Test-Path $zoneDest)) {
  Write-Host "downloading taxi_zone_lookup.csv ..."
  Invoke-WebRequest -Uri $ZoneUrl -OutFile $zoneDest
}
Get-ChildItem $DataDir | Format-Table Name, Length
