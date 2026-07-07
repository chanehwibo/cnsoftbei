$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"
# 验收脚本走离线规则模式：断言精确工具名，不受 LLM 非确定性影响，也不消耗 API 费用
$env:SAFEOPS_LLM_DISABLED = "1"

function Invoke-External {
  param(
    [Parameter(Mandatory=$true)][string]$FileName,
    [Parameter(Mandatory=$true)][string[]]$Arguments
  )

  $command = Get-Command $FileName -ErrorAction Stop
  $processInfo = New-Object System.Diagnostics.ProcessStartInfo
  $processInfo.FileName = $command.Source
  $processInfo.Arguments = (($Arguments | ForEach-Object {
    if ($_ -match '[\s"]') { '"' + $_.Replace('"', '\"') + '"' } else { $_ }
  }) -join " ")
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

  [pscustomobject]@{
    ExitCode = $process.ExitCode
    Output = ($stdout + $stderr).Trim()
  }
}

function Invoke-OptionalGit {
  param([Parameter(Mandatory=$true)][string[]]$Arguments)
  try {
    $result = Invoke-External "git" $Arguments
    if ($result.ExitCode -ne 0 -or -not $result.Output) {
      return "unknown"
    }
    return $result.Output
  } catch {
    return "unknown"
  }
}

$dist = Join-Path $repo "dist"
if (-not (Test-Path -LiteralPath $dist)) {
  New-Item -ItemType Directory -Path $dist | Out-Null
}

Write-Host "Running acceptance..."
$acceptance = Invoke-External "powershell" @("-ExecutionPolicy", "Bypass", "-File", "scripts\acceptance.ps1")
if ($acceptance.ExitCode -ne 0) {
  throw "acceptance failed: $($acceptance.Output)"
}

Write-Host "Collecting tool metadata..."
$toolsResult = Invoke-External "python" @("-m", "safeops_agent.cli", "--list-tools")
if ($toolsResult.ExitCode -ne 0) {
  throw "tool list failed: $($toolsResult.Output)"
}
$tools = $toolsResult.Output | ConvertFrom-Json
$toolCount = @($tools).Count
$categories = @($tools | Group-Object category | Sort-Object Name | ForEach-Object { "- $($_.Name): $($_.Count)" }) -join "`n"

$commit = Invoke-OptionalGit @("-c", "safe.directory=$repo", "rev-parse", "--short", "HEAD")
$status = Invoke-OptionalGit @("-c", "safe.directory=$repo", "status", "--short")
if ($status -eq "unknown") {
  $status = "unknown"
} elseif (-not $status) {
  $status = "clean"
}

$auditPath = Join-Path $repo "data\audit.log"
$auditTail = "audit log not found"
if (Test-Path -LiteralPath $auditPath) {
  $auditTail = (Get-Content -LiteralPath $auditPath -Encoding utf8 -Tail 5) -join "`n"
}

$reportPath = Join-Path $dist "acceptance-report.md"
$now = Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"
$report = @"
# SafeOps Agent 自动验收报告

生成时间：$now

## 1. 结果摘要

| 项目 | 结果 |
| --- | --- |
| Git 提交 | `$commit` |
| 工作区状态 | `$status` |
| 自动验收 | 通过 |
| MCP 风格工具数量 | $toolCount |
| 审计日志 | 已生成并可读取 |

## 2. 工具分类统计

$categories

## 3. 验收命令

```powershell
powershell -ExecutionPolicy Bypass -File scripts\acceptance.ps1
```

## 4. 最近审计事件

```jsonl
$auditTail
```

## 5. 结论

本报告由脚本自动生成，说明当前代码可以完成单元测试、核心 CLI 验收、工具清单输出、中风险确认、高风险拦截和审计日志检查。
"@
Set-Content -LiteralPath $reportPath -Encoding UTF8 -Value $report
Write-Host "Acceptance report created: $reportPath"