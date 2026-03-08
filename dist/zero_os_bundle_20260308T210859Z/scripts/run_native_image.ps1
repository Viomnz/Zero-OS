param(
  [string]$ImagePath = ".\\build\\native_os\\zero_os_native.img"
)

$ErrorActionPreference = "Stop"
$qemu = Get-Command qemu-system-i386 -ErrorAction SilentlyContinue
if (-not $qemu) {
  $fallback = "C:\Program Files\qemu\qemu-system-i386.exe"
  if (Test-Path $fallback) {
    $qemu = @{ Source = $fallback }
  } else {
    throw "qemu-system-i386 not found. Install QEMU and rerun."
  }
}
if (-not (Test-Path $ImagePath)) {
  throw "Image not found: $ImagePath"
}

& $qemu.Source -drive format=raw,file=$ImagePath
