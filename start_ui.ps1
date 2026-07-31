$ErrorActionPreference = "Stop"

# Windows PowerShell 5.1 reads this file as ANSI unless it is saved with a
# UTF-8 BOM, and decodes child-process stdout with the console codepage.
# Both must be UTF-8 or non-ASCII interface text arrives as mojibake.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

Write-Host "AI Music Lab: http://127.0.0.1:7860  (Russian: /ru)"
Write-Host "Stop: Ctrl+C"
conda run --no-capture-output -n ai-music-ui python -m music_lab_ui.app
