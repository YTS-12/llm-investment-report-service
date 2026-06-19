# Meilisearch 로컬 서버 실행 스크립트
# 사용법: 프로젝트 루트에서  ./scripts/run_meilisearch.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$masterKey = ""
$meiliHost = "http://127.0.0.1:7700"

if (Test-Path ".env") {
    foreach ($line in Get-Content ".env") {
        if ($line -match '^\s*MEILI_MASTER_KEY\s*=\s*(.+?)\s*$') { $masterKey = $matches[1].Trim() }
        if ($line -match '^\s*MEILI_HOST\s*=\s*(.+?)\s*$')       { $meiliHost = $matches[1].Trim() }
    }
}

$addr = ([System.Uri]$meiliHost).Authority
if ([string]::IsNullOrWhiteSpace($addr)) { $addr = "127.0.0.1:7700" }

Write-Host "Starting Meilisearch on $addr (db: .\data.ms)"
& ".\tools\meilisearch-windows-amd64.exe" --master-key $masterKey --db-path ".\data.ms" --http-addr $addr
