$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"
python -m safeops_agent.config_check @args
exit $LASTEXITCODE
