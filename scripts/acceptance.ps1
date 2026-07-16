$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"
# 验收脚本走离线规则模式：断言精确工具名，不受 LLM 非确定性影响，也不消耗 API 费用
$env:SAFEOPS_LLM_DISABLED = "1"

function ConvertTo-CommandLineArgument {
  param([Parameter(Mandatory=$true)][string]$Argument)
  if ($Argument.Length -eq 0) {
    return '""'
  }
  if ($Argument -notmatch '[\s"]') {
    return $Argument
  }
  return '"' + $Argument.Replace('"', '\"') + '"'
}

function Invoke-PythonStep {
  param(
    [Parameter(Mandatory=$true)][string]$Name,
    [Parameter(Mandatory=$true)][string[]]$Arguments,
    [int[]]$AllowedExitCodes = @(0),
    [string]$MustContain = ""
  )

  Write-Host "`n[ACCEPT] $Name"

  $processInfo = New-Object System.Diagnostics.ProcessStartInfo
  $processInfo.FileName = "python"
  $processInfo.Arguments = (($Arguments | ForEach-Object { ConvertTo-CommandLineArgument $_ }) -join " ")
  $processInfo.WorkingDirectory = $repo
  $processInfo.UseShellExecute = $false
  $processInfo.RedirectStandardOutput = $true
  $processInfo.RedirectStandardError = $true
  $processInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
  $processInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8

  $process = New-Object System.Diagnostics.Process
  $process.StartInfo = $processInfo
  [void]$process.Start()
  $stdout = $process.StandardOutput.ReadToEnd()
  $stderr = $process.StandardError.ReadToEnd()
  $process.WaitForExit()
  $exitCode = $process.ExitCode

  $text = ($stdout + $stderr)
  if ($text.Trim().Length -gt 0) {
    Write-Host $text.TrimEnd()
  }
  if ($AllowedExitCodes -notcontains $exitCode) {
    throw "Step '$Name' failed with exit code $exitCode. Allowed: $($AllowedExitCodes -join ', ')"
  }
  if ($MustContain -and ($text -notlike "*$MustContain*")) {
    throw "Step '$Name' output does not contain expected text: $MustContain"
  }
}

Write-Host "SafeOps Agent acceptance started."

Invoke-PythonStep "unit tests" @("-m", "unittest", "discover", "-s", "tests")
Invoke-PythonStep "configuration validation" @("-m", "safeops_agent.config_check") @(0) "配置校验通过"
Invoke-PythonStep "list MCP-style tools" @("-m", "safeops_agent.cli", "--list-tools") @(0) '"name": "system.info"'
Invoke-PythonStep "low risk system info" @("-m", "safeops_agent.cli", "查看系统信息", "--json") @(0) '"tool": "system.info"'
Invoke-PythonStep "low risk resources" @("-m", "safeops_agent.cli", "查看CPU和内存", "--json") @(0) '"tool": "system.resources"'
Invoke-PythonStep "low risk listening ports" @("-m", "safeops_agent.cli", "查看监听端口", "--json") @(0) '"tool": "network.listening_ports"'
Invoke-PythonStep "medium risk confirmation required" @("-m", "safeops_agent.cli", "重启 nginx 服务", "--json") @(1) '"requires_confirmation": true'
Invoke-PythonStep "high risk sensitive path blocked" @("-m", "safeops_agent.cli", "覆盖 /etc/passwd", "--json") @(1) '"risk": "HIGH"'

if (-not (Test-Path -LiteralPath ".\data\audit.log")) {
  throw "audit log was not created at data\audit.log"
}
Invoke-PythonStep "signed audit verification" @("-m", "safeops_agent.cli", "--verify-audit") @(0) '"ok": true'

Write-Host "`n[ACCEPT] recent audit events"
Get-Content -LiteralPath ".\data\audit.log" -Encoding utf8 -Tail 5

Write-Host "`nSafeOps Agent acceptance passed."
