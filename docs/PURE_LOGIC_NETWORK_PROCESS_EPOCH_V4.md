# Pure Logic Network and Process Consolidation Epoch v4

This epoch attacks two broad bypass families identified by the enforcement audit: raw network transport and distributed process execution.

## Network result

Network authority is no longer treated as a single undifferentiated permission.

A live capability lease must now survive all of these checks at the sink:

- current, unexpired lease;
- read/write network authority;
- exact destination host authority or explicit wildcard;
- explicit local/private-network authority for loopback/private destinations;
- explicit credential-transmit authority when authentication material is attached;
- HTTP/HTTPS scheme restriction.

The standalone chat-model router was migrated from raw urllib transport to the shared leased network client. Without a live network lease it fails closed and falls back to the local response path.

Raw `urlopen` outside the trusted secure primitive remains a promotion blocker and is enumerated by `transport_process_migration_audit.py`.

## Process result

This epoch deliberately does not introduce a generic process runner. Instead it introduces capability classification for concrete executable families:

- Python
- tests
- Git/GitHub CLI
- containers
- service control
- shells

Unknown and dynamically computed executable targets remain unclassified and therefore non-authoritative.

The migration audit groups existing subprocess sinks by required process scope and flags dynamic/unclassified targets. This converts a large distributed process surface into a finite migration queue without pretending classification is execution mediation.

## Pure Logic promotion rule

Network consolidation is complete only when no raw network primitive remains outside the trusted transport boundary.

Process classification is complete only when every identified process target maps to an explicit process capability. Central process execution mediation is still a separate unresolved requirement.

Passing these static conditions does not certify runtime security, dependency behavior, native code, concurrency, firmware, hardware, or unseen transport mechanisms.
