# Setup do Tutor de Ingles local (Emily). Roda uma unica vez, precisa de internet
# (baixa ~7-8GB: PyTorch+CUDA, modelo Ollama, voz Piper, modelo Whisper).
# Depois desse setup, o app funciona 100% offline.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "== 0/5: Verificando pre-requisitos ==" -ForegroundColor Cyan

# --- Python 3.12 -------------------------------------------------------
$pythonExe = $null
$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pyLauncher) {
    & py -3.12 -c "print('ok')" *> $null
    if ($LASTEXITCODE -eq 0) { $pythonExe = "py-3.12" }
}
if (-not $pythonExe) {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "C:\Python312\python.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $pythonExe = $c; break }
    }
}
if (-not $pythonExe) {
    throw "Python 3.12 nao encontrado. Instale em https://www.python.org/downloads/release/python-3120/ " +
          "(marque 'Add python.exe to PATH' no instalador) e rode este script de novo."
}
Write-Host "Python 3.12 encontrado: $pythonExe" -ForegroundColor DarkGray

# --- Ollama --------------------------------------------------------------
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw "Ollama nao encontrado. Instale em https://ollama.com/download (Windows) e rode este script de novo."
}
Write-Host "Ollama encontrado." -ForegroundColor DarkGray

# --- GPU NVIDIA + VRAM: decide automaticamente quais modelos usar --------
$hasNvidia = Get-Command nvidia-smi -ErrorAction SilentlyContinue
$vramMB = 0
if ($hasNvidia) {
    try {
        $vramMB = [int]((& nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits) | Select-Object -First 1)
    } catch {
        $hasNvidia = $null
    }
}

if ($hasNvidia -and $vramMB -ge 7000) {
    # 8GB+ de VRAM (ex: RTX 4060 8GB): modelo de linguagem maior cabe folgado
    $tier = "gpu-8gb"
    $ollamaModel = "llama3.1:8b-instruct-q4_K_M"
    $whisperModel = "small.en"
    $sttDevice = "cuda"
    $sttCompute = "int8_float16"
} elseif ($hasNvidia -and $vramMB -ge 4000) {
    # GPUs de 4-7GB: modelo de linguagem menor, mas ainda na GPU
    $tier = "gpu-4to7gb"
    $ollamaModel = "llama3.2:3b-instruct-q4_K_M"
    $whisperModel = "small.en"
    $sttDevice = "cuda"
    $sttCompute = "int8_float16"
} elseif ($hasNvidia) {
    # GPU NVIDIA mas com pouca VRAM (<4GB)
    $tier = "gpu-low-vram"
    $ollamaModel = "llama3.2:3b-instruct-q4_K_M"
    $whisperModel = "base.en"
    $sttDevice = "cuda"
    $sttCompute = "int8"
} else {
    # Sem GPU NVIDIA: tudo na CPU, modelos menores para manter a conversa fluida
    $tier = "cpu-only"
    $ollamaModel = "llama3.2:3b-instruct-q4_K_M"
    $whisperModel = "base.en"
    $sttDevice = "cpu"
    $sttCompute = "int8"
}

if ($hasNvidia) {
    Write-Host "GPU NVIDIA detectada com ${vramMB}MB de VRAM (perfil: $tier)." -ForegroundColor DarkGray
} else {
    Write-Host "Nenhuma GPU NVIDIA detectada - vai rodar tudo na CPU (perfil: $tier)." -ForegroundColor Yellow
    Write-Host "Funciona, mas as respostas do tutor serao mais lentas do que com GPU." -ForegroundColor Yellow
}
Write-Host "Modelos escolhidos: LLM=$ollamaModel | Whisper=$whisperModel | device=$sttDevice" -ForegroundColor DarkGray

Write-Host "== 1/5: Criando ambiente virtual Python ==" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    if ($pythonExe -eq "py-3.12") {
        & py -3.12 -m venv .venv
    } else {
        & $pythonExe -m venv .venv
    }
}
& .\.venv\Scripts\pip install --upgrade pip

Write-Host "== 2/5: Instalando PyTorch (com CUDA se houver GPU NVIDIA) ==" -ForegroundColor Cyan
if ($hasNvidia) {
    & .\.venv\Scripts\pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
} else {
    & .\.venv\Scripts\pip install torch torchaudio
}

Write-Host "== 3/5: Instalando demais dependencias ==" -ForegroundColor Cyan
& .\.venv\Scripts\pip install -r requirements.txt

Write-Host "== 4/5: Baixando modelos (LLM via Ollama + voz Piper + Whisper) ==" -ForegroundColor Cyan

Write-Host "Baixando modelo Ollama: $ollamaModel (pode demorar alguns minutos)..."
ollama pull $ollamaModel

$voiceDir = Join-Path $root "data\voices"
New-Item -ItemType Directory -Force -Path $voiceDir | Out-Null

$voiceBase = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_female/medium/en_US-hfc_female-medium"
$onnxPath = Join-Path $voiceDir "en_US-hfc_female-medium.onnx"
$jsonPath = Join-Path $voiceDir "en_US-hfc_female-medium.onnx.json"

if (-not (Test-Path $onnxPath)) {
    Write-Host "Baixando voz Piper (en_US-hfc_female-medium)..."
    Invoke-WebRequest -Uri "$voiceBase.onnx" -OutFile $onnxPath
    Invoke-WebRequest -Uri "$voiceBase.onnx.json" -OutFile $jsonPath
} else {
    Write-Host "Voz Piper ja baixada, pulando."
}

$binDir = Join-Path $root "bin"
$piperExe = Join-Path $binDir "piper\piper.exe"
if (-not (Test-Path $piperExe)) {
    Write-Host "Baixando binario do Piper TTS (engine local, sem pip)..."
    New-Item -ItemType Directory -Force -Path $binDir | Out-Null
    $zipPath = Join-Path $binDir "piper_windows_amd64.zip"
    Invoke-WebRequest -Uri "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip" -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath $binDir -Force
    Remove-Item $zipPath
} else {
    Write-Host "Binario do Piper ja baixado, pulando."
}

Write-Host "Baixando modelo Whisper (STT): $whisperModel..." -ForegroundColor Cyan
& .\.venv\Scripts\python -c "from app.stt import SpeechToText; import os; os.environ.pop('HF_HUB_OFFLINE', None); SpeechToText(model_size='$whisperModel', device='$sttDevice', compute_type='$sttCompute')"

Write-Host "== 5/5: Ajustando config.yaml para o hardware detectado ==" -ForegroundColor Cyan
$configPath = Join-Path $root "config.yaml"
$configText = Get-Content $configPath -Raw -Encoding UTF8
$configText = $configText -replace 'model: "llama3\.1:8b-instruct-q4_K_M"', "model: `"$ollamaModel`""
$configText = $configText -replace 'model_size: "small\.en"(\s+# tiny\.en, base\.en, small\.en, medium\.en)', "model_size: `"$whisperModel`"`$1"
$configText = $configText -replace 'device: "cuda"(\s+# "cuda" ou "cpu" \(troque se faltar VRAM\))', "device: `"$sttDevice`"`$1"
$configText = $configText -replace 'compute_type: "int8_float16"(\s+# bom equil.brio velocidade/qualidade na 4060)', "compute_type: `"$sttCompute`"`$1"
Set-Content -Path $configPath -Value $configText -Encoding UTF8 -NoNewline
Write-Host "config.yaml atualizado (perfil: $tier)." -ForegroundColor DarkGray

Write-Host "Registrando o comando 'run emily' no PATH do usuario..." -ForegroundColor Cyan
$scriptsDir = Join-Path $root "scripts"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$pathEntries = $userPath -split ";" | Where-Object { $_ -ne "" }
if ($pathEntries -notcontains $scriptsDir) {
    $newPath = if ($userPath) { "$userPath;$scriptsDir" } else { $scriptsDir }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "Adicionado ao PATH. Abra um terminal NOVO para o comando 'run emily' funcionar de qualquer pasta." -ForegroundColor DarkGray
} else {
    Write-Host "Ja estava no PATH, pulando." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Setup concluido. A partir de agora nao precisa mais de internet." -ForegroundColor Green
Write-Host "Para rodar o tutor, abra um terminal novo e digite: run emily" -ForegroundColor Green
