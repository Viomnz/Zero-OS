# Security Runbooks

## Incident: Malware/Finding Spike
- Command: `antivirus monitor tick .`
- Command: `triad balance run`
- Command: `enterprise siem emit high malware_spike`

## Incident: Integrity Drift
- Command: `zero ai gap status`
- Command: `zero ai gap fix`
- Command: `enterprise immutable audit export`

## Incident: Recovery
- Command: `enterprise dr drill rto=120`
- Command: `enterprise rollback run critical`
