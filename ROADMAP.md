# Zero OS Roadmap

## Versioning Plan
This roadmap tracks practical milestones from current state to stable open source release.

## v0.2 Foundation Hardening
Target:
- Stabilize current layered runtime and security controls

Deliverables:
1. Expand attack simulation coverage
2. Add CI checks for key runtime commands
3. Add dashboard endpoint tests
4. Improve docs for operator flows
5. Lock command compatibility for launcher and dashboard

Exit Criteria:
- Test suite green
- Security checks reproducible
- No regression in guarded file restore behavior

## v0.3 Open Contributor Scale
Target:
- Make contributions safer and faster

Deliverables:
1. Contributor templates for new capabilities
2. Plugin security validation checklist
3. Structured threat test fixtures
4. Runtime telemetry summaries in markdown reports
5. Stable API contracts for local dashboard endpoints

Exit Criteria:
- External contributors can add lanes with tests
- Security posture remains stable after extensions

## v1.0 Stable Open System Release
Target:
- Public open source release with documented governance and stable interfaces

Deliverables:
1. Frozen core architecture docs
2. Signed release process and rollback guides
3. Long-run daemon reliability validation
4. Public issue templates for bugs and security
5. Reference deployment guide for local and lab setups

Exit Criteria:
- Release checklist complete
- Docs match implementation
- Layered defenses validated against attack simulation set

## Active Backlog Highlights
1. Expand malicious pattern detection and anomaly scoring
2. Improve false-positive handling near thresholds
3. Add per-channel command rate limits
4. Add richer observability dashboards
5. Build reproducible benchmark profiles for low-end and high-end PCs

