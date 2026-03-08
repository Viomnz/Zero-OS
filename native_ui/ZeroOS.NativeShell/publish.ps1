param(
  [string]$Configuration = "Release",
  [string]$Runtime = "win-x64",
  [string]$Output = "",
  [switch]$SelfContained = $true,
  [switch]$SingleFile = $true
)

$ErrorActionPreference = "Stop"
$Project = Join-Path $PSScriptRoot "ZeroOS.NativeShell.csproj"
if (-not $Output) {
  $Output = Join-Path $PSScriptRoot "publish"
}

if (Test-Path $Output) {
  Remove-Item -Recurse -Force $Output
}

dotnet publish $Project `
  -c $Configuration `
  -r $Runtime `
  --self-contained $($SelfContained.ToString().ToLowerInvariant()) `
  -p:PublishSingleFile=$($SingleFile.ToString().ToLowerInvariant()) `
  -p:IncludeNativeLibrariesForSelfExtract=true `
  -o $Output

Write-Output "Published ZeroOS.NativeShell to $Output"
