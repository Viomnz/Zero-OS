param(
  [string]$Configuration = "Release",
  [string]$Runtime = "win-x64",
  [string]$Output = ""
)

$ErrorActionPreference = "Stop"
$Project = Join-Path $PSScriptRoot "ZeroOS.NativeShell.csproj"
if (-not $Output) {
  $Output = Join-Path $PSScriptRoot "publish"
}

dotnet publish $Project `
  -c $Configuration `
  -r $Runtime `
  --self-contained false `
  -p:PublishSingleFile=false `
  -o $Output

Write-Output "Published ZeroOS.NativeShell to $Output"
