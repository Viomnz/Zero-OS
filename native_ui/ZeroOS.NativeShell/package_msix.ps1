param(
  [string]$Version = "",
  [string]$Runtime = "win-x64"
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PublishDir = Join-Path $ScriptRoot "publish"
$MsixDir = Join-Path $ScriptRoot "msix"
$ManifestTemplate = Join-Path $ScriptRoot "Package.appxmanifest"
$SigningConfigPath = Join-Path $ScriptRoot "signing.json"

if (-not (Test-Path $PublishDir)) {
  throw "Publish output not found. Run publish.ps1 first."
}

function Get-ToolPath([string]$toolName) {
  $direct = Get-Command $toolName -ErrorAction SilentlyContinue
  if ($direct) {
    return $direct.Source
  }
  $kitsRoot = "C:\Program Files (x86)\Windows Kits\10"
  $match = Get-ChildItem -Path $kitsRoot -Recurse -Filter $toolName -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -like "*\\x64\\*" -or $_.FullName -like "*App Certification Kit*" } |
    Select-Object -First 1
  if ($match) {
    return $match.FullName
  }
  throw "$toolName not found."
}

function Read-ProjectVersion() {
  $project = Join-Path $ScriptRoot "ZeroOS.NativeShell.csproj"
  [xml]$xml = Get-Content -Path $project
  return ($xml.Project.PropertyGroup.Version | Select-Object -First 1)
}

if (-not $Version) {
  $Version = Read-ProjectVersion
}
if (-not $Version) {
  $Version = "1.0.0"
}
$VersionQuad = if ($Version.Split('.').Count -eq 4) { $Version } else { "$Version.0" }

if (-not (Test-Path $ManifestTemplate)) {
  throw "Package.appxmanifest not found."
}

$makeappx = Get-ToolPath "makeappx.exe"
$signtool = Get-ToolPath "signtool.exe"
$StageDir = Join-Path $MsixDir "staging"
$PackagePath = Join-Path $MsixDir "ZeroOS.NativeShell_$VersionQuad_$Runtime.msix"
$SummaryPath = Join-Path $MsixDir "package_summary.json"
$AssetsDir = Join-Path $ScriptRoot "assets"

if (Test-Path $StageDir) {
  Remove-Item -Recurse -Force $StageDir
}
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
New-Item -ItemType Directory -Force -Path $MsixDir | Out-Null

Get-ChildItem -Path $PublishDir -Force | Copy-Item -Destination $StageDir -Recurse -Force
Copy-Item -Path $AssetsDir -Destination (Join-Path $StageDir "assets") -Recurse -Force

$manifest = Get-Content -Path $ManifestTemplate -Raw
$signingConfig = Get-Content -Path $SigningConfigPath -Raw | ConvertFrom-Json
$publisher = if ($signingConfig.publisher) { [string]$signingConfig.publisher } else { "CN=ZeroOS" }
[xml]$manifestXml = $manifest
$ns = New-Object System.Xml.XmlNamespaceManager($manifestXml.NameTable)
$ns.AddNamespace("appx", "http://schemas.microsoft.com/appx/manifest/foundation/windows10")
$identity = $manifestXml.SelectSingleNode("/appx:Package/appx:Identity", $ns)
if (-not $identity) {
  throw "Identity node not found in Package.appxmanifest."
}
$identity.SetAttribute("Publisher", $publisher)
$identity.SetAttribute("Version", $VersionQuad)
$settings = New-Object System.Xml.XmlWriterSettings
$settings.Encoding = New-Object System.Text.UTF8Encoding($false)
$settings.Indent = $true
$writer = [System.Xml.XmlWriter]::Create((Join-Path $StageDir "AppxManifest.xml"), $settings)
$manifestXml.Save($writer)
$writer.Close()

if (Test-Path $PackagePath) {
  Remove-Item -Force $PackagePath
}

& $makeappx pack /d $StageDir /p $PackagePath /o | Out-Null
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $PackagePath)) {
  throw "makeappx failed to create the MSIX package."
}

$signed = $false
$signingStatus = "unsigned"
if ($signingConfig.enabled -and $signingConfig.pfx_path) {
  $pfxPath = [string]$signingConfig.pfx_path
  $passwordEnv = [string]$signingConfig.pfx_password_env
  $passwordValue = if ($passwordEnv) { [Environment]::GetEnvironmentVariable($passwordEnv) } else { "" }
  if (-not (Test-Path $pfxPath)) {
    throw "Signing enabled but pfx_path not found: $pfxPath"
  }
  if (-not $passwordValue) {
    throw "Signing enabled but password environment variable '$passwordEnv' is empty."
  }
  & $signtool sign /fd SHA256 /f $pfxPath /p $passwordValue /tr $signingConfig.timestamp_url /td SHA256 $PackagePath | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "signtool failed to sign the MSIX package."
  }
  $signed = $true
  $signingStatus = "signed"
}

$summary = @{
  ok = $true
  version = $VersionQuad
  runtime = $Runtime
  msix = $PackagePath
  signed = $signed
  signing_status = $signingStatus
  publisher = $publisher
  publish_dir = $PublishDir
  stage_dir = $StageDir
  makeappx = $makeappx
  signtool = $signtool
}
$summary | ConvertTo-Json -Depth 4 | Set-Content -Path $SummaryPath -Encoding UTF8

Write-Output "MSIX package created at $PackagePath"
Write-Output "Signing status: $signingStatus"
