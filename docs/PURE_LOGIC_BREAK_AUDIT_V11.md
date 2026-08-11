# Pure Logic Break Audit v11

This audit attacks the current Pure Logic implementation as an authorized defensive review of Zero-OS. Findings are architectural failure classes, not claims of real-world compromise.

## 1. Symmetric root-of-trust contradiction — CRITICAL

The authority issuer signs attestations with HMAC and `verify_attestation()` recomputes the HMAC using `_issuer_secret(cwd)`.

That means the runtime verifier must possess the same secret that signs authority. A future separate-process issuer cannot simultaneously satisfy:

- private signing key unavailable to ordinary runtime; and
- ordinary runtime independently verifies HMAC attestations.

### Required repair

Use asymmetric signatures for authority artifacts. The issuer alone holds the private key. Runtime and sinks receive only a pinned public verification key. Production promotion must reject a verifier that can retrieve signing material.

## 2. Runtime authority trace can be rewritten consistently — CRITICAL

`runtime_trace.jsonl` is hash chained but not signed or externally anchored. A writer able to replace the file can fabricate a complete sequence and recompute every `previous_event_digest` and `event_digest`.

The current verifier proves internal consistency of the presented file, not historical authenticity.

### Required repair

Periodically sign/anchor trace heads outside the ordinary runtime trust domain. Candidate mechanisms include an isolated issuer signature, TPM monotonic state, append-only external log, or independent remote witness. Certification must require an anchor newer than the action being certified.

## 3. Security Control Plane history has the same forgery class — CRITICAL

The control-plane history links revisions and state digests, but state and history are stored in the same writable trust domain. A same-privilege writer can replace both and construct a self-consistent alternate history.

### Required repair

Sign each promoted revision or anchor each control-plane head in an independent trust domain. Recovery must compare local state with the independently retained head.

## 4. Path Law non-authority guard is syntactic, not semantic — HIGH

The current guard detects literal forbidden call names only inside functions/classes whose name looks like Path Logic. It can be evaded by:

- aliasing an authority function;
- calling through a wrapper;
- `getattr` / dynamic dispatch;
- using a selector function with a neutral name;
- moving authority minting to a helper outside the recognized Path context.

Therefore `run_on_every_candidate_change` is a useful policy but does not yet demonstrate that Path Law remains non-authoritative after every change.

### Required repair

Build a taint/call-graph rule: data/control flow originating in Path selection may consume already-authorized option sets, but no path-selection-derived flow may reach authority creation, scope certification, objective authorization, identity verification, capability minting, execution-ticket minting, or promotion. Dynamic/unknown dispatch reachable from Path logic should make scope contested rather than pass.

## 5. Whole-repository execution surface remains broader than Pure Logic mediation — HIGH

Repository search still finds direct `subprocess.run` use across tools, platform adapters, native/store code, antivirus process inspection, production-core utilities, source evolution, and other areas. Static discovery alone does not prove those sinks bypass authority, but it proves the mediation surface remains broad and must be traced per call path.

### Required repair

Move from symbol inventory to interprocedural reachability: entry point -> authority decision -> artifact -> consume -> sink. Any consequential sink without a demonstrated authority path blocks promotion.

## Root conclusion

The next large result should not be another policy layer. It should be **Asymmetric Authority + Externally Anchored Reality History + Semantic Non-Authority Proofs**.

Target architecture:

```
Pure Logic constitutional decision
        -> isolated issuer
        -> private key never enters runtime
        -> asymmetric signed authority token
        -> runtime verifies with pinned public key
        -> sink acts
        -> outcome evidence
        -> signed/externally anchored trace head
```

Path Law remains downstream of authority and is re-audited on every candidate change, but promotion relies on semantic reachability/taint evidence rather than literal function names.
