# Zero OS Roadmap

## Versioning Plan
This roadmap tracks practical milestones from current state to stable open source release.

## Strategic Focus (Now)
Execution split:
- 80% AI/runtime platform
- 20% kernel R&D foundation

Reason:
- Ship user value now with working layers.
- Build kernel path without stalling product.

## Parallel Track A (Primary): AI/Runtime Platform
Target:
- Deliver a stable smart OS layer across Windows, Linux, macOS through Hyperlayer.

Deliverables:
1. Hyperlayer adapters parity for file/process/network actions.
2. Harden Zero-AI loop: novelty -> adaptation -> model evolution -> traceability.
3. Security and integrity: cure firewall, guard baseline, rollback, quarantine.
4. Unified dashboard observability for adaptation/evolution/health/security.
5. Package/runtime policy for open source contributors.

Exit Criteria:
- Cross-platform command parity for core actions.
- Reliability and security tests pass in CI.
- No unauthorized guard rollback on approved files.

## Parallel Track B (Secondary): From-Scratch Kernel R&D
Target:
- Build a real kernel foundation in phases while maintaining platform stability.

Deliverables:
1. Syscall specification (`docs/kernel/syscalls.md`).
2. Scheduler prototype model and test harness.
3. Memory manager design and page model.
4. Driver interface contract (disk/network/display/input).
5. Boot path and safe-mode recovery design.

Exit Criteria:
- Kernel design docs versioned and test-backed prototypes exist.
- Clear migration map from host-bridged Hyperlayer to native kernel modules.

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

## Top User Choice Track
Reference execution plan:
- `docs/TOP_USER_CHOICE_90D.md`

Reference measurable targets:
- `zero_os_config/top_user_choice_targets.json`
