$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$packagePath = Join-Path $repo "dist\cnsoftbei-submission.zip"
if (-not (Test-Path -LiteralPath $packagePath)) {
  powershell -ExecutionPolicy Bypass -File scripts\package.ps1
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($packagePath)
try {
  $entries = @($zip.Entries | ForEach-Object { $_.FullName.Replace('\', '/') })
  $required = @(
    "README.md",
    "pyproject.toml",
    "src/safeops_agent/agent.py",
    "src/safeops_agent/tools/diagnostics.py",
    "tests/test_agent.py",
    "tests/test_audit.py",
    "config/app.yaml",
    "web/index.html",
    "web/app.js",
    "scripts/acceptance.ps1",
    "scripts/report.ps1",
    "scripts/web-smoke.ps1",
    "scripts/verify-package.ps1",
    "docs/INITIAL_SUBMISSION.md",
    "docs/FEATURE_HIGHLIGHTS_PLAN.md",
    "docs/TODO_LIST.md"
  )
  foreach ($item in $required) {
    if ($entries -notcontains $item) {
      throw "missing package entry: $item"
    }
  }

  $forbiddenPatterns = @(
    ".git/",
    "data/audit.log",
    "data/pending_actions.json",
    "__pycache__/",
    "dist/"
  )
  $forbiddenEntries = @("config/llm.local.yaml", ".env")
  foreach ($entry in $entries) {
    if ($forbiddenEntries -contains $entry) {
      throw "forbidden package entry: $entry"
    }
    foreach ($pattern in $forbiddenPatterns) {
      if ($entry -like "*$pattern*") {
        throw "forbidden package entry: $entry"
      }
    }
  }

  Write-Host "Package verified: $packagePath"
  Write-Host "Entries: $($entries.Count)"
} finally {
  $zip.Dispose()
}
