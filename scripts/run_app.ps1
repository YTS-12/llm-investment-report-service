# FastAPI 앱 실행 스크립트
# 사용법: 프로젝트 루트에서  ./scripts/run_app.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Write-Host "Starting uvicorn on http://127.0.0.1:8010"
& $py -m uvicorn app:app --host 127.0.0.1 --port 8010
