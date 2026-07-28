# Roda o tutor de ingles Emily. Se ainda nao foi feito o setup (primeira vez
# nesta maquina), roda o setup automaticamente antes (precisa de internet so
# nessa primeira vez).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$piperExe = Join-Path $root "bin\piper\piper.exe"
$voiceOnnx = Join-Path $root "data\voices\en_US-hfc_female-medium.onnx"

$needsSetup = -not (Test-Path $venvPython) -or -not (Test-Path $piperExe) -or -not (Test-Path $voiceOnnx)

if ($needsSetup) {
    Write-Host "Primeira execucao (ou setup incompleto) - rodando setup.ps1 primeiro..." -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "setup.ps1")
}

Write-Host "Iniciando Emily..." -ForegroundColor Cyan
& $venvPython -m app.main
