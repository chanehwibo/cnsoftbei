$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$dist = Join-Path $repo "dist"
if (-not (Test-Path -LiteralPath $dist)) {
  New-Item -ItemType Directory -Path $dist | Out-Null
}

$packagePath = Join-Path $dist "cnsoftbei-submission.zip"
$staging = Join-Path $dist "cnsoftbei-submission-staging"
$repoResolved = (Resolve-Path -LiteralPath $repo).Path.TrimEnd('\')
$distResolved = (Resolve-Path -LiteralPath $dist).Path.TrimEnd('\')

function Assert-UnderPath($Path, $Parent) {
  $resolved = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path).TrimEnd('\')
  if (-not ($resolved -eq $Parent -or $resolved.StartsWith($Parent + '\'))) {
    throw "refusing to operate outside expected directory: $resolved"
  }
}

function Test-ExcludedPackagePath($FullName) {
  $normalized = $FullName.Replace('\', '/')
  return (
    $normalized -like "*/.git/*" -or
    $normalized -like "*/dist/*" -or
    $normalized -like "*/data/audit.log" -or
    $normalized -like "*/__pycache__/*" -or
    $normalized -like "*.pyc"
  )
}

Assert-UnderPath $staging $distResolved
if (Test-Path -LiteralPath $staging) {
  Remove-Item -LiteralPath $staging -Recurse -Force
}
New-Item -ItemType Directory -Path $staging | Out-Null

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

foreach ($item in $items) {
  $source = (Resolve-Path -LiteralPath $item).Path
  if ((Get-Item -LiteralPath $source).PSIsContainer) {
    Get-ChildItem -LiteralPath $source -Recurse -File -Force | ForEach-Object {
      if (Test-ExcludedPackagePath $_.FullName) {
        return
      }
      $relative = $_.FullName.Substring($repoResolved.Length).TrimStart('\', '/')
      $target = Join-Path $staging $relative
      $targetDir = Split-Path -Parent $target
      if (-not (Test-Path -LiteralPath $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir | Out-Null
      }
      Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    }
  } else {
    if (Test-ExcludedPackagePath $source) {
      continue
    }
    $relative = $source.Substring($repoResolved.Length).TrimStart('\', '/')
    $target = Join-Path $staging $relative
    $targetDir = Split-Path -Parent $target
    if (-not (Test-Path -LiteralPath $targetDir)) {
      New-Item -ItemType Directory -Path $targetDir | Out-Null
    }
    Copy-Item -LiteralPath $source -Destination $target -Force
  }
}

$archiveItems = @(Get-ChildItem -LiteralPath $staging -Force)
if ($archiveItems.Count -eq 0) {
  throw "no files staged for package"
}
Compress-Archive -LiteralPath $archiveItems.FullName -DestinationPath $packagePath -Force
Remove-Item -LiteralPath $staging -Recurse -Force
Write-Host "Submission package created: $packagePath"