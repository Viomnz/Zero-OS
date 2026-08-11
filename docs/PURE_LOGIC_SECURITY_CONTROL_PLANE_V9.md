# Zero-OS Pure Logic Security Control Plane v9

v9 moves the highest-value security settings out of ordinary feature-local authority and into one protected control plane.

## Constitutional rule

Security mechanisms may observe, score, detect, recommend, quarantine, or recover only within authority granted by the Pure Logic constitution. Security mechanisms do not own the policy that defines their own authority.

## Protected control surfaces

The correction plane now treats these as protected targets:

- authority root and authority runtime trace;
- security control plane;
- antivirus policy and suppressions;
- antivirus feed signing keys;
- Cure Firewall policy;
- recovery policy;
- security key rotation.

A normal runtime writer receives no standing write authority to those targets.

## Atomic security state

`security_control_plane.py` stores a versioned state containing antivirus policy, suppressions, firewall policy, recovery policy, and signing-key generations. A successful security-policy transaction:

1. requires a freshly consumed constitution-authorized `policy_change` handoff;
2. applies the requested batch as one new control revision;
3. links the new revision to the previous state digest;
4. records a history event;
5. exposes the new revision and digest.

This prevents a security hardening routine from silently granting itself policy authority merely because its intent is defensive.

## Security signing

`security_signing.py` replaces the design target for the legacy deterministic antivirus signing key. New feed envelopes use random 256-bit control-plane key material, key generations, control-plane revision binding, tamper detection, and minimum-version rollback rejection.

The legacy antivirus signer is not yet migrated and remains a promotion blocker.

## Runtime authority traces

`authority_runtime_trace.py` creates hash-chained events for the causal authority path. A complete trace can require:

- constitutional decision;
- issuer attestation;
- runtime consume;
- sink acknowledgement;
- independent outcome verification.

A trace is certified only when required events are present and the principal, authority, objective, action, subject, and state revision remain consistent through the recorded path.

This is stronger evidence than static symbol or call-edge presence, but it is still software-generated evidence and is not treated as external reality.

## Issuer privilege boundary

`authority_issuer_boundary.py` distinguishes four scopes:

- `IN_PROCESS_DEVELOPMENT`;
- `SEPARATE_PROCESS`;
- `OS_PROTECTED`;
- `HARDWARE_BACKED`.

The current software issuer is explicitly classified as development scope because ordinary runtime shares its privilege domain and may access the software-held key. Production Root-of-Trust authority is denied until the issuer is separated by process and OS identity, with hardware backing required for claims that depend on a hardware key boundary.

## Promotion

`pure_logic_v9_promotion.py` refuses promotion when any of these remain unresolved:

- authority runtime integration failure;
- incomplete security-control-plane migration;
- non-production issuer privilege boundary;
- missing runtime authority trace;
- failing/unexecuted CI;
- missing fresh adversarial audit.

Even successful v9 promotion would remain provisional in demonstrated scope and would not permit a general claim that Zero-OS is secure.

## Current deliberate blockers

The v9 branch intentionally remains blocked because:

1. legacy `antivirus.py` still contains its deterministic path-derived feed key;
2. legacy antivirus policy/suppression mutators are not yet routed through the security control plane;
3. the current authority issuer is in-process software, not a separate OS/hardware trust domain;
4. runtime trace events are defined but not yet wired across every real authority path;
5. CI and fresh external/adversarial execution have not yet survived.

These blockers are failure records, not TODO decoration. Promotion should remain denied until they are independently resolved.
