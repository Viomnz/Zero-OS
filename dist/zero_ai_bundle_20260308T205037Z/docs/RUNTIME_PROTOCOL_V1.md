# Runtime Protocol v1

Defines the protocol layer above OS adapters and below app/runtime network control.

## Scope
- Core API surface: `file`, `net`, `ui`, `permissions`, `identity`
- Adapter contract per OS
- Capability negotiation handshake
- Package attestation chain
- Runtime compatibility range
- Deprecation policy entries

## Commands
- `python src/main.py "runtime protocol status"`
- `python src/main.py "runtime protocol security status"`
- `python src/main.py "runtime protocol security grade"`
- `python src/main.py "runtime protocol security maximize"`
- `python src/main.py "runtime protocol security set strict=<on|off> min=<low|baseline|strict|high>"`
- `python src/main.py "runtime protocol signer allow <name>"`
- `python src/main.py "runtime protocol signer revoke <name>"`
- `python src/main.py "runtime protocol key rotate"`
- `python src/main.py "runtime protocol adapter <windows|linux|macos|android|ios>"`
- `python src/main.py "runtime protocol adapter allowlist <os> hash=<sha256>"`
- `python src/main.py "runtime protocol nonce issue node=<id>"`
- `python src/main.py "runtime protocol handshake os=<os> cpu=<cpu> arch=<arch> security=<level>"`
- `python src/main.py "runtime protocol secure handshake os=<os> cpu=<cpu> arch=<arch> security=<level> nonce=<n> proof=<p>"`
- `python src/main.py "runtime protocol proof preview os=<os> cpu=<cpu> arch=<arch> security=<level> nonce=<n>"`
- `python src/main.py "runtime protocol attest path=<path> signer=<name>"`
- `python src/main.py "runtime protocol verify path=<path> signer=<name> signature=<sig>"`
- `python src/main.py "runtime protocol compatibility version=<v>"`
- `python src/main.py "runtime protocol deprecate api=<name> remove_after=<date>"`
- `python src/main.py "runtime protocol audit status"`
