$ErrorActionPreference = "Stop"

$matches = Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -like "*safeops_agent.web_server*"
}

if (-not $matches) {
  Write-Host "No SafeOps Web process found."
  exit 0
}

foreach ($process in $matches) {
  Write-Host "Stopping SafeOps Web process: $($process.ProcessId)"
  Stop-Process -Id $process.ProcessId -Force
}
