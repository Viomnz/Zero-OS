# Alert Escalation Templates

## Critical
- Trigger: ransomware/integrity failure/critical malware finding
- Command sequence:
  1. `enterprise siem emit critical incident-critical`
  2. `enterprise rollback run critical`
  3. `self repair run`
  4. `triad balance run`

## High
- Trigger: high-severity findings, repeated monitor alerts
- Command sequence:
  1. `enterprise siem emit high incident-high`
  2. `antivirus agent run . auto_quarantine=true`
  3. `cure firewall agent run pressure 90`

## Medium
- Trigger: medium-risk heuristics only
- Command sequence:
  1. `enterprise siem emit medium incident-medium`
  2. `antivirus scan .`
  3. `triad ops tick`

## Low
- Trigger: informational events
- Command sequence:
  1. `enterprise siem emit low incident-low`
  2. `enterprise security status`
