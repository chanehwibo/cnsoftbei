$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$env:PYTHONPATH = "src"

$requests = @(
  "查看系统信息",
  "查看CPU和内存",
  "查看监听端口",
  "查看 nginx 服务状态",
  "重启 nginx 服务",
  "覆盖 /etc/passwd",
  "查询 nginx 软件包"
)

foreach ($request in $requests) {
  Write-Host "`n>>> $request"
  python -m safeops_agent.cli $request --json
  if ($LASTEXITCODE -ne 0) {
    Write-Host "command returned non-zero as expected for blocked requests"
  }
}

Write-Host "`nRecent audit events:"
Get-Content -LiteralPath ".\data\audit.log" -Encoding utf8 -Tail 8
