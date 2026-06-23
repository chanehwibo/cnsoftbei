$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$env:PYTHONPATH = "src"
python -c "import json; from safeops_agent.mcp_server import McpToolService; print(json.dumps(McpToolService().list_tools(), ensure_ascii=False, indent=2))"
