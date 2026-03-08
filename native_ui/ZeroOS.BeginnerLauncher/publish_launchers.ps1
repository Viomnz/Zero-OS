param(
  [string]$Configuration = "Release",
  [string]$Runtime = "win-x64"
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Project = Join-Path $ScriptRoot "ZeroOS.BeginnerLauncher.csproj"
$PublishDir = Join-Path $ScriptRoot "publish"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $ScriptRoot)

if (Test-Path $PublishDir) {
  Remove-Item -Recurse -Force $PublishDir
}

dotnet publish $Project `
  -c $Configuration `
  -r $Runtime `
  --self-contained true `
  -p:PublishSingleFile=true `
  -p:IncludeNativeLibrariesForSelfExtract=true `
  -o $PublishDir

$launcher = Join-Path $PublishDir "ZeroOS.BeginnerLauncher.exe"
if (-not (Test-Path $launcher)) {
  throw "Published launcher exe not found."
}

$targets = @(
  "Zero OS QuickStart.exe",
  "Open Zero OS.exe",
  "Open Zero OS Native Shell.exe"
)

foreach ($name in $targets) {
  Copy-Item -Force $launcher (Join-Path $RepoRoot $name)
}

Write-Output "Beginner launcher EXEs created in $RepoRoot"
