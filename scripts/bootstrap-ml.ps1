param(
    [switch]$Force,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$serviceRoot = Join-Path $repoRoot "ml-service"
$venvRoot = Join-Path $serviceRoot ".venv"
$pythonExe = Join-Path $venvRoot "Scripts\python.exe"
$artifactPath = Join-Path $serviceRoot "artifacts\url_xgb.joblib"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    python -m venv $venvRoot
}

if (-not $SkipInstall) {
    & $pythonExe -m pip install -r (Join-Path $serviceRoot "requirements.txt")
}

if ($Force -and (Test-Path -LiteralPath $artifactPath)) {
    Remove-Item -LiteralPath $artifactPath
}

Push-Location $serviceRoot
try {
    if (-not (Test-Path -LiteralPath $artifactPath)) {
        & $pythonExe -m src.train `
            --data data/sample_urls.csv `
            --output artifacts/url_xgb.joblib `
            --metrics artifacts/metrics.json
    }

    & $pythonExe -c "from src.features import FEATURE_NAMES; from src.model import UrlRiskModel; model = UrlRiskModel('artifacts/url_xgb.joblib'); print(f'ML artifact ready: {len(FEATURE_NAMES)} features, version={model.version}')"
} finally {
    Pop-Location
}
