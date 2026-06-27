$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$dist = Join-Path $repo "dist"
if (-not (Test-Path -LiteralPath $dist)) {
  New-Item -ItemType Directory -Path $dist | Out-Null
}

$packagePath = Join-Path $dist "cnsoftbei-submission.zip"
$items = @(
  "README.md",
  "pyproject.toml",
  ".gitignore",
  "config",
  "demo",
  "docs",
  "scripts",
  "src",
  "tests",
  "web"
) | Where-Object { Test-Path -LiteralPath $_ }

Compress-Archive -LiteralPath $items -DestinationPath $packagePath -Force
Write-Host "Submission package created: $packagePath"
