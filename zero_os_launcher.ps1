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
function Daemon-Health { python ai_from_scratch/daemon_ctl.py health }
function Daemon-Baseline { python ai_from_scratch/daemon_ctl.py baseline }
function Daemon-Security { python ai_from_scratch/daemon_ctl.py security }
function Daemon-SecurityPolicy {
  param([string]$KV)
  python ai_from_scratch/daemon_ctl.py security-policy --kv $KV
}
function Daemon-ReputationScan { python ai_from_scratch/daemon_ctl.py reputation-scan }
function Daemon-Stabilize { python ai_from_scratch/daemon_ctl.py stabilize }
function Daemon-TrustFile {
  param([string]$ArgsText)
  $parts = $ArgsText.Split(",")
  if ($parts.Length -lt 2) { throw "Use trust-file:<path>,<score>[,level][,note]" }
  $file = $parts[0]
  $score = $parts[1]
  $level = if ($parts.Length -ge 3) { $parts[2] } else { "trusted" }
  $note = if ($parts.Length -ge 4) { $parts[3] } else { "" }
  python ai_from_scratch/daemon_ctl.py trust-file --file $file --score $score --level $level --note $note
}
function Queue-Scan { python ai_from_scratch/daemon_ctl.py task --prompt "scan" }
function Queue-Task {
  param([string]$Prompt)
  if (-not $Prompt) { throw "Prompt required for task" }
  python ai_from_scratch/daemon_ctl.py task --prompt $Prompt
}
function Smart-Flow {
  param([string]$WorkspacePath)
  if ($WorkspacePath) {
    python ai_from_scratch/daemon_ctl.py smart-flow --workspace $WorkspacePath
  } else {
    python ai_from_scratch/daemon_ctl.py smart-flow
  }
}

function Show-Readiness { python src/main.py "os readiness --json" }
function Fix-Missing { python src/main.py "os missing fix" }
function Sandbox-Status { python src/main.py "sandbox status" }
function Sandbox-Allow { param([string]$Prefix) python src/main.py "sandbox allow $Prefix" }
function Sandbox-Deny { param([string]$Prefix) python src/main.py "sandbox deny $Prefix" }
function Update-Create { param([string]$Version) python src/main.py "update package create $Version" }
function Update-Apply { param([string]$Version) python src/main.py "update apply $Version" }
function Update-Rollback { python src/main.py "update rollback" }
function Deps-List { python src/main.py "deps list" }
function Jobs-List { python src/main.py "jobs list" }
function Observability-Report { python src/main.py "observability report" }
function Snapshot-Create { python src/main.py "snapshot create" }
function Snapshot-List { python src/main.py "snapshot list" }
function Error-Playbook { python src/main.py "error playbook show" }
function Release-Info { python src/main.py "release init" }
function Benchmark-Run { python src/main.py "benchmark run" }
function Unified-Shell {
  param([string]$CommandText)
  if (-not $CommandText) { throw "Command required" }
  python src/main.py "shell run $CommandText"
}
function Codex-Suggest {
  param([string]$Goal)
  python src/main.py "codex: suggest route: $Goal"
}
function Codex-Run {
  param([string]$Goal)
  python src/main.py "codex: $Goal"
}
function Codex-Option {
  param([string]$Payload)
  $i = $Payload.IndexOf(":")
  if ($i -lt 1) { throw "Use codex-option:<n>:<goal>" }
  $n = $Payload.Substring(0, $i)
  $goal = $Payload.Substring($i + 1)
  python src/main.py "codex: option ${n}: $goal"
}
function Show-Monitor { Get-Content -Raw .zero_os\runtime\zero_ai_monitor.json -ErrorAction SilentlyContinue }
function Show-Output { Get-Content -Tail 80 .zero_os\runtime\zero_ai_output.txt -ErrorAction SilentlyContinue }
function Show-ScanReport { Get-Content -Raw .zero_os\runtime\zero_ai_scan_report.json -ErrorAction SilentlyContinue }
function Kill-Agent {
  Daemon-Stop
  Stop-DashboardServer
  Write-Output "Emergency kill complete"
}

function Suggest-Actions {
  param([string]$Goal)
  if (-not $Goal) {
    Write-Output "Provide a goal: .\zero_os_launcher.ps1 suggest:<your goal>"
    return
  }
  $g = $Goal.ToLower()
  $suggestions = New-Object System.Collections.Generic.List[string]
  if ($g -match "dashboard|ui|open|see") { $suggestions.Add("open-dashboard") }
  if ($g -match "start|run|daemon|agent") { $suggestions.Add("start-daemon") }
  if ($g -match "health|virus|secure|security|safe") {
    $suggestions.Add("health-agent")
    $suggestions.Add("security-agent")
    $suggestions.Add("reputation-scan")
  }
  if ($g -match "fix|missing|setup|install") {
    $suggestions.Add("readiness")
    $suggestions.Add("missing-fix")
  }
  if ($g -match "backup|restore|snapshot|rollback") {
    $suggestions.Add("snapshot-create")
    $suggestions.Add("snapshot-list")
    $suggestions.Add("update-rollback")
  }
  if ($g -match "update|upgrade|release|version") {
    $suggestions.Add("update-create:v1")
    $suggestions.Add("update-apply:v1")
    $suggestions.Add("release-info")
  }
  if ($g -match "code|build|create|plan|search|goal|idea") {
    $suggestions.Add("codex-suggest:$Goal")
    $suggestions.Add("codex-run:$Goal")
  }
  if ($g -match "monitor|log|status|observe|metrics") {
    $suggestions.Add("status-daemon")
    $suggestions.Add("monitor")
    $suggestions.Add("observability")
    $suggestions.Add("output")
  }
  if ($suggestions.Count -eq 0) {
    $suggestions.Add("menu")
    $suggestions.Add("readiness")
    $suggestions.Add("codex-suggest:$Goal")
    $suggestions.Add("security-agent")
  }
  $uniq = $suggestions | Select-Object -Unique
  Write-Output "Suggested actions for: $Goal"
  $i = 1
  foreach ($s in $uniq | Select-Object -First 9) {
    Write-Output ("{0}. {1}" -f $i, $s)
    $i++
  }
}

function Guide-Next {
  Write-Output "Zero-OS Guided Start"
  Write-Output "1. readiness"
  Write-Output "2. missing-fix (if score is low)"
  Write-Output "3. baseline-agent"
  Write-Output "4. security-agent"
  Write-Output "5. start-daemon"
  Write-Output "6. open-dashboard"
  Write-Output "7. codex-suggest:<goal>"
  Write-Output "8. codex-run:<goal>"
}

function First-Run {
  python tools/first_run_setup.py
}
function Native-Build {
  param([string]$ArgsText)
  if ($ArgsText) {
    $parts = $ArgsText.Split(",")
    $img = if ($parts.Length -ge 1 -and $parts[0]) { $parts[0] } else { "zero_os_native.img" }
    $size = if ($parts.Length -ge 2 -and $parts[1]) { $parts[1] } else { "1440" }
    powershell -ExecutionPolicy Bypass -File .\scripts\build_boot_media.ps1 -ImageName $img -SizeKb $size
  } else {
    powershell -ExecutionPolicy Bypass -File .\scripts\build_boot_media.ps1
  }
}
function Native-Run {
  param([string]$ImagePath)
  if ($ImagePath) {
    powershell -ExecutionPolicy Bypass -File .\scripts\run_native_image.ps1 -ImagePath $ImagePath
  } else {
    powershell -ExecutionPolicy Bypass -File .\scripts\run_native_image.ps1
  }
}
function Native-Toolchain {
  python tools/native_dev_ecosystem.py toolchain-status
}
function Native-BuildAll {
  powershell -ExecutionPolicy Bypass -File .\scripts\native_build_all.ps1
}
function Native-Smoke {
  param([string]$TimeoutSec)
  if ($TimeoutSec) {
    powershell -ExecutionPolicy Bypass -File .\scripts\native_qemu_smoke.ps1 -Timeout $TimeoutSec
  } else {
    powershell -ExecutionPolicy Bypass -File .\scripts\native_qemu_smoke.ps1
  }
}

function Show-Menu {
  @"
Zero-OS One Command Launcher

Usage:
  .\zero_os_launcher.ps1 <action>

Actions:
  menu                      Show this options list
  guide                     Guided startup sequence
  first-run                 One-command first-run setup + hardening
  native-build              Build standalone native OS boot image
  native-build:<img,size>   Build custom image name and size KB
  native-run                Boot image in QEMU (qemu-system-i386 required)
  native-run:<path>         Boot selected image path in QEMU
  native-toolchain          Show cross-compiler and emulator toolchain status
  native-build-all          Build kernel image + userland modules + manifest
  native-smoke              Run QEMU integration smoke test
  native-smoke:<seconds>    Run QEMU smoke test with timeout
  suggest:<goal>            Suggest up to 9 best actions for user goal

  open-dashboard            Start local dashboard server and print URL
  start-dashboard           Start local dashboard server only
  stop-dashboard            Stop local dashboard server

  start-daemon              Start Zero-AI daemon
  stop-daemon               Stop Zero-AI daemon
  status-daemon             Show daemon status
  health-agent              Run integrity health check
  baseline-agent            Rebuild integrity baseline
  security-agent            Run layered security report
  security-policy:<kv>      Set policy
  reputation-scan           Scan executable/script reputation trust
  stabilize-agent           Rebuild baseline + restart + refresh monitor
  trust-file:<p,s,l,n>      Sign file reputation
  kill-agent                Emergency stop daemon + dashboard
  scan                      Queue scan task (syntax + tests)
  task:<text>               Queue custom AI task
  smart-flow                Auto smart flow for current workspace path
  smart-flow:<path>         Auto smart flow for selected workspace path

  codex-suggest:<goal>      Show route options only (no execution)
  codex-run:<goal>          Run codex goal with auto route
  codex-option:<n>:<goal>   Run selected codex route option index

  readiness                 Show OS readiness JSON
  missing-fix               Scaffold missing OS layers
  sandbox-status            Show command sandbox policy
  sandbox-allow:<prefix>    Allow command prefix in sandbox
  sandbox-deny:<prefix>     Deny command prefix in sandbox
  update-create:<ver>       Create signed local update package
  update-apply:<ver>        Apply signed update package
  update-rollback           Roll back to last snapshot
  deps-list                 Show dependency registry
  jobs-list                 Show priority job queue
  observability             Show runtime observability report
  snapshot-create           Create recovery snapshot
  snapshot-list             List snapshots
  error-playbook            Show remediation playbooks
  release-info              Initialize/show release state
  benchmark                 Run local performance benchmark
  shell:<command>           Unified shell run (terminal + powershell merged)
  terminal:<command>        Alias of shell
  powershell:<command>      Alias of shell

  monitor                   Show monitor JSON
  output                    Show latest daemon output tail
  scan-report               Show latest scan report JSON
"@
}

switch -Regex ($Action) {
  "^menu$" { Show-Menu; break }
  "^guide$" { Guide-Next; break }
  "^first-run$" { First-Run; break }
  "^native-build$" { Native-Build; break }
  "^native-build:(.+)$" { Native-Build -ArgsText $Matches[1]; break }
  "^native-run$" { Native-Run; break }
  "^native-run:(.+)$" { Native-Run -ImagePath $Matches[1]; break }
  "^native-toolchain$" { Native-Toolchain; break }
  "^native-build-all$" { Native-BuildAll; break }
  "^native-smoke$" { Native-Smoke; break }
  "^native-smoke:(.+)$" { Native-Smoke -TimeoutSec $Matches[1]; break }
  "^suggest:(.+)$" { Suggest-Actions -Goal $Matches[1]; break }

  "^open-dashboard$" { Open-Dashboard; break }
  "^start-dashboard$" { Start-DashboardServer; break }
  "^stop-dashboard$" { Stop-DashboardServer; break }

  "^start-daemon$" { Daemon-Start; break }
  "^stop-daemon$" { Daemon-Stop; break }
  "^status-daemon$" { Daemon-Status; break }
  "^health-agent$" { Daemon-Health; break }
  "^baseline-agent$" { Daemon-Baseline; break }
  "^security-agent$" { Daemon-Security; break }
  "^security-policy:(.+)$" { Daemon-SecurityPolicy -KV $Matches[1]; break }
  "^reputation-scan$" { Daemon-ReputationScan; break }
  "^stabilize-agent$" { Daemon-Stabilize; break }
  "^trust-file:(.+)$" { Daemon-TrustFile -ArgsText $Matches[1]; break }
  "^kill-agent$" { Kill-Agent; break }
  "^scan$" { Queue-Scan; break }
  "^task:(.+)$" { Queue-Task -Prompt $Matches[1]; break }
  "^smart-flow$" { Smart-Flow; break }
  "^smart-flow:(.+)$" { Smart-Flow -WorkspacePath $Matches[1]; break }

  "^codex-suggest:(.+)$" { Codex-Suggest -Goal $Matches[1]; break }
  "^codex-run:(.+)$" { Codex-Run -Goal $Matches[1]; break }
  "^codex-option:(.+)$" { Codex-Option -Payload $Matches[1]; break }

  "^readiness$" { Show-Readiness; break }
  "^missing-fix$" { Fix-Missing; break }
  "^sandbox-status$" { Sandbox-Status; break }
  "^sandbox-allow:(.+)$" { Sandbox-Allow -Prefix $Matches[1]; break }
  "^sandbox-deny:(.+)$" { Sandbox-Deny -Prefix $Matches[1]; break }
  "^update-create:(.+)$" { Update-Create -Version $Matches[1]; break }
  "^update-apply:(.+)$" { Update-Apply -Version $Matches[1]; break }
  "^update-rollback$" { Update-Rollback; break }
  "^deps-list$" { Deps-List; break }
  "^jobs-list$" { Jobs-List; break }
  "^observability$" { Observability-Report; break }
  "^snapshot-create$" { Snapshot-Create; break }
  "^snapshot-list$" { Snapshot-List; break }
  "^error-playbook$" { Error-Playbook; break }
  "^release-info$" { Release-Info; break }
  "^benchmark$" { Benchmark-Run; break }
  "^shell:(.+)$" { Unified-Shell -CommandText $Matches[1]; break }
  "^terminal:(.+)$" { Unified-Shell -CommandText $Matches[1]; break }
  "^powershell:(.+)$" { Unified-Shell -CommandText $Matches[1]; break }

  "^monitor$" { Show-Monitor; break }
  "^output$" { Show-Output; break }
  "^scan-report$" { Show-ScanReport; break }

  default { Show-Menu; break }
}
