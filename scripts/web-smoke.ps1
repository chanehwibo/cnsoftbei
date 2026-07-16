$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"
# 验收脚本走离线规则模式：断言精确工具名，不受 LLM 非确定性影响，也不消耗 API 费用
$env:SAFEOPS_LLM_DISABLED = "1"

$process = $null
try {
  $process = Start-Process -FilePath "python" -ArgumentList @("-m", "safeops_agent.web_server") -WorkingDirectory $repo -PassThru -WindowStyle Hidden
  Start-Sleep -Milliseconds 900

  $health = $null
  for ($i = 0; $i -lt 20; $i++) {
    try {
      $health = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health" -Method Get -TimeoutSec 2
      break
    } catch {
      Start-Sleep -Milliseconds 300
    }
  }
  if (-not $health -or -not $health.ok) {
    throw "health check failed"
  }

  $tools = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/tools" -Method Get -TimeoutSec 3
  if (-not $tools.ok -or @($tools.tools).Count -lt 1) {
    throw "tool list api failed"
  }

  $body = @{ request = "查看系统信息" } | ConvertTo-Json -Compress
  $agent = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/agent" -Method Post -Body $body -ContentType "application/json; charset=utf-8" -TimeoutSec 5
  if (-not $agent.ok -or $agent.tool -ne "system.info") {
    throw "agent api failed"
  }

  $audit = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/audit" -Method Get -TimeoutSec 3
  if (-not $audit.ok) {
    throw "audit api failed"
  }

  Write-Host "Web smoke passed: health/tools/agent/audit APIs are available."
} finally {
  if ($process -and -not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
    $process.WaitForExit(3000) | Out-Null
  }
}
