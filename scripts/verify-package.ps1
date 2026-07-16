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
    "src/safeops_agent/audit/logger.py",
    "src/safeops_agent/mcp_stdio.py",
    "src/safeops_agent/security/pending.py",
    "src/safeops_agent/tools/diagnostics.py",
    "src/safeops_agent/resources/config/app.yaml",
    "src/safeops_agent/resources/web/index.html",
    "tests/test_agent.py",
    "tests/test_audit.py",
    "tests/test_packaging.py",
    "tests/test_web_server.py",
    "config/app.yaml",
    "web/index.html",
    "web/app.js",
    "scripts/acceptance.ps1",
    "scripts/report.ps1",
    "scripts/web-smoke.ps1",
    "scripts/verify-package.ps1",
    "docs/ARCHITECTURE.md",
    "docs/BEGINNER_OPERATION_MANUAL.md",
    "docs/DEMO_SCRIPT.md",
    "docs/DEPLOYMENT.md",
    "docs/DESIGN_TECHNICAL_DOCUMENT.md",
    "docs/DEVELOPMENT_LOG.md",
    "docs/ERROR_CODES.md",
    "docs/LLM_INTEGRATION.md",
    "docs/MCP_TOOLS.md",
    "docs/SAFETY_GUARDRAILS.md",
    "docs/SCRIPTS.md",
    "docs/TEST_PLAN_AND_REPORT.md"
  )
  foreach ($item in $required) {
    if ($entries -notcontains $item) {
      throw "missing package entry: $item"
    }
  }

  $forbiddenPatterns = @(
    ".git/",
    "data/",
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
