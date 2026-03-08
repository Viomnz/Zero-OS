param(
  [string]$Version = "1.0.0.0"
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PublishDir = Join-Path $ScriptRoot "publish"
$MsixDir = Join-Path $ScriptRoot "msix"

if (-not (Test-Path $PublishDir)) {
  throw "Publish output not found. Run publish.ps1 first."
}

New-Item -ItemType Directory -Force -Path $MsixDir | Out-Null

@"
MSIX packaging scaffold for Zero OS Native Shell

Version: $Version
Publish directory: $PublishDir

Next production steps:
1. Add app icon .ico assets
2. Add Package.appxmanifest
3. Sign with trusted certificate
4. Build MSIX using makeappx / signtool
"@ | Set-Content -Path (Join-Path $MsixDir "README.txt")

Write-Output "MSIX scaffold created in $MsixDir"
