# Root of Trust v8 design note

This branch is a break record. The implementation epoch will branch from it and replace caller-mintable authority artifacts with issuer-attested artifacts.

Primary invariant: a lease or ticket is not authority merely because an object with the right fields exists. The sink must verify an attestation from the authority issuer over the exact principal, objective, authority claim, action/capability, state revision, scope, issue time, expiry, and nonce.

Software-only attestation is still not a hardware trust root. A same-privilege attacker that can read the issuer secret or modify the verifier remains outside the demonstrated scope until process/OS/hardware isolation is added.
