param(
  [int]$Timeout = 5
)
$ErrorActionPreference = "Stop"
python tools/native_dev_ecosystem.py qemu-smoke --timeout $Timeout
