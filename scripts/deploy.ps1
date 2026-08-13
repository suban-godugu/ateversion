# Deploy Wafer Yield Intelligence (Docker Compose)
param(
  [switch]$Seed,
  [switch]$Down,
  [switch]$Wipe
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "docker-compose.yml"))) {
  $Root = $PSScriptRoot
  if (-not (Test-Path (Join-Path $Root "docker-compose.yml"))) {
    $Root = Get-Location
  }
}
Set-Location $Root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "Docker is not installed or not on PATH." -ForegroundColor Red
  Write-Host "Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
  exit 1
}

$EnvFile = Join-Path $Root ".env.deploy"
if (-not (Test-Path $EnvFile)) {
  Copy-Item (Join-Path $Root ".env.deploy.example") $EnvFile
  Write-Host "Created .env.deploy — edit secrets (JWT_SECRET, POSTGRES_PASSWORD) then re-run." -ForegroundColor Yellow
  exit 2
}

if ($Wipe) {
  docker compose --env-file $EnvFile down -v
  exit $LASTEXITCODE
}

if ($Down) {
  docker compose --env-file $EnvFile down
  exit $LASTEXITCODE
}

docker compose --env-file $EnvFile up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($Seed) {
  Write-Host "Seeding reference floor data..."
  docker compose --env-file $EnvFile exec api python -m app.ingestion.seed
}

Write-Host ""
Write-Host "Deployed. Open http://localhost" -ForegroundColor Green
Write-Host "Health: http://localhost/api/health"
