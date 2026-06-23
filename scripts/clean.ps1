$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

Get-ChildItem -LiteralPath $repo -Recurse -Directory -Filter "__pycache__" | ForEach-Object {
  Remove-Item -LiteralPath $_.FullName -Recurse -Force
}

Get-ChildItem -LiteralPath $repo -Recurse -Directory -Filter ".pytest_cache" | ForEach-Object {
  Remove-Item -LiteralPath $_.FullName -Recurse -Force
}

Write-Host "Python cache directories removed."
