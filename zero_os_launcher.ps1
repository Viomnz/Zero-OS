param(
  [string]$Action = "menu"
)

$ErrorActionPreference = "Stop"
$Base = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Base

function Start-DashboardServer {
  $running = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
  if ($running) {
    Write-Output "Dashboard server already running on :8765"
    return
  }
  Start-Process -FilePath python -ArgumentList "ai_from_scratch/dashboard_server.py" -WorkingDirectory $Base | Out-Null
  Start-Sleep -Seconds 1
  Write-Output "Dashboard server started on :8765"
}

function Open-Dashboard {
  Start-DashboardServer
  Write-Output "Open in browser: http://127.0.0.1:8765/zero_os_dashboard.html"
}

function Stop-DashboardServer {
  $conns = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
  if (-not $conns) {
    Write-Output "Dashboard server not running"
    return
  }
  $procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($procId in $procIds) {
    try { Stop-Process -Id $procId -Force -ErrorAction Stop } catch {}
  }
  Write-Output "Dashboard server stopped"
}

function Daemon-Start { python ai_from_scratch/daemon_ctl.py start }
function Daemon-Stop { python ai_from_scratch/daemon_ctl.py stop }
function Daemon-Status { python ai_from_scratch/daemon_ctl.py status }
function Queue-Scan { python ai_from_scratch/daemon_ctl.py task --prompt "scan" }
function Queue-Task {
  param([string]$Prompt)
  if (-not $Prompt) { throw "Prompt required for task" }
  python ai_from_scratch/daemon_ctl.py task --prompt $Prompt
}

function Show-Readiness { python src/main.py "os readiness --json" }
function Fix-Missing { python src/main.py "os missing fix" }
function Show-Monitor { Get-Content -Raw .zero_os\runtime\zero_ai_monitor.json -ErrorAction SilentlyContinue }
function Show-Output { Get-Content -Tail 80 .zero_os\runtime\zero_ai_output.txt -ErrorAction SilentlyContinue }
function Show-ScanReport { Get-Content -Raw .zero_os\runtime\zero_ai_scan_report.json -ErrorAction SilentlyContinue }

function Show-Menu {
  @"
Zero-OS One Command Launcher

Usage:
  .\zero_os_launcher.ps1 <action>

Actions:
  menu                      Show this options list
  open-dashboard            Start local dashboard server and print URL
  start-dashboard           Start local dashboard server only
  stop-dashboard            Stop local dashboard server

  start-daemon              Start Zero-AI daemon
  stop-daemon               Stop Zero-AI daemon
  status-daemon             Show daemon status
  scan                      Queue scan task (syntax + tests)
  task:<text>               Queue custom AI task (example: task:self awareness pressure balance)

  readiness                 Show OS readiness JSON
  missing-fix               Scaffold missing OS layers

  monitor                   Show monitor JSON
  output                    Show latest daemon output tail
  scan-report               Show latest scan report JSON

Quick examples:
  .\zero_os_launcher.ps1 open-dashboard
  .\zero_os_launcher.ps1 start-daemon
  .\zero_os_launcher.ps1 scan
  .\zero_os_launcher.ps1 readiness
"@
}

switch -Regex ($Action) {
  "^menu$" { Show-Menu; break }
  "^open-dashboard$" { Open-Dashboard; break }
  "^start-dashboard$" { Start-DashboardServer; break }
  "^stop-dashboard$" { Stop-DashboardServer; break }

  "^start-daemon$" { Daemon-Start; break }
  "^stop-daemon$" { Daemon-Stop; break }
  "^status-daemon$" { Daemon-Status; break }
  "^scan$" { Queue-Scan; break }
  "^task:(.+)$" { Queue-Task -Prompt $Matches[1]; break }

  "^readiness$" { Show-Readiness; break }
  "^missing-fix$" { Fix-Missing; break }

  "^monitor$" { Show-Monitor; break }
  "^output$" { Show-Output; break }
  "^scan-report$" { Show-ScanReport; break }

  default { Show-Menu; break }
}
