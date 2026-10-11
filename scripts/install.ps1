$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Install Python 3.12 (including the Python launcher) and run this script again."
}
& py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "Python 3.12 is required." }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& .\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed. Check the output above." }

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warning "FFmpeg is missing. Install it with: winget install --id Gyan.FFmpeg --exact"
}
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Warning "Install Ollama from https://ollama.com/download/windows for local document generation."
}
Write-Host "Dependencies installed. Next:"
Write-Host ".\.venv\Scripts\python.exe scripts\download_model.py"
Write-Host "ollama pull qwen3:8b"
Write-Host ".\start.bat"
