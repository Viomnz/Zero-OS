param(
  [string]$Version = "",
  [string]$Runtime = "win-x64"
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Project = Join-Path $ScriptRoot "ZeroOS.NativeShell.csproj"
$PublishDir = Join-Path $ScriptRoot "publish"
$InstallersDir = Join-Path $ScriptRoot "installers"

if (-not (Test-Path $PublishDir)) {
  throw "Publish output not found. Run publish.ps1 first."
}

if (-not $Version) {
  [xml]$projectXml = Get-Content -Path $Project
  $Version = $projectXml.Project.PropertyGroup.Version | Select-Object -First 1
}

if (-not $Version) {
  $Version = "0.0.0"
}

$PackageName = "zero-os-native-shell-$Version-$Runtime"
$PackageDir = Join-Path $InstallersDir $PackageName
$ZipPath = Join-Path $InstallersDir "$PackageName.zip"

if (Test-Path $PackageDir) {
  Remove-Item -Recurse -Force $PackageDir
}

New-Item -ItemType Directory -Force -Path $PackageDir | Out-Null
Get-ChildItem -Path $PublishDir -Force | Copy-Item -Destination $PackageDir -Recurse -Force

$CmdLauncher = @"
@echo off
setlocal
cd /d "%~dp0"
start "" ".\ZeroOS.NativeShell.exe"
"@
Set-Content -Path (Join-Path $PackageDir "Launch Zero OS Native Shell.cmd") -Value $CmdLauncher -Encoding ASCII

$PsLauncher = @"
Set-Location -Path `$PSScriptRoot
Start-Process -FilePath (Join-Path `$PSScriptRoot 'ZeroOS.NativeShell.exe')
"@
Set-Content -Path (Join-Path $PackageDir "Launch Zero OS Native Shell.ps1") -Value $PsLauncher -Encoding UTF8

$Readme = @"
Zero OS Native Shell Portable Package

Version: $Version
Runtime: $Runtime

Start here:
1. Double-click 'Launch Zero OS Native Shell.cmd'
2. In the app, use Quick Start
3. Click Run First-Run
4. Click Open Shell UI

GitHub users should not need to learn Zero OS commands first.
"@
Set-Content -Path (Join-Path $PackageDir "README.txt") -Value $Readme -Encoding UTF8

$Manifest = @{
  package = $PackageName
  version = $Version
  runtime = $Runtime
  created_utc = [DateTime]::UtcNow.ToString("o")
  publish_dir = $PublishDir
  entrypoints = @(
    "ZeroOS.NativeShell.exe",
    "Launch Zero OS Native Shell.cmd",
    "Launch Zero OS Native Shell.ps1"
  )
} | ConvertTo-Json -Depth 4
Set-Content -Path (Join-Path $PackageDir "package_manifest.json") -Value $Manifest -Encoding UTF8

New-Item -ItemType Directory -Force -Path $InstallersDir | Out-Null
if (Test-Path $ZipPath) {
  Remove-Item -Force $ZipPath
}
Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $ZipPath -Force

Write-Output "Portable installer package created in $PackageDir"
Write-Output "Portable installer zip created at $ZipPath"
