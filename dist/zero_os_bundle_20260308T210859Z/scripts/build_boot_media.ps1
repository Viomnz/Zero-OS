param(
  [string]$ImageName = "zero_os_native.img",
  [int]$SizeKb = 1440
)

$ErrorActionPreference = "Stop"
$Base = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $Base
Set-Location $Root

python tools/build_native_image.py --image-name $ImageName --size-kb $SizeKb
