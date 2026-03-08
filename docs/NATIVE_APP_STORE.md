# Native App Store

Native app store adapter layer for OS-targeted installs in the Zero runtime stack.

## Commands
- `python src/main.py "native store status"`
- `python src/main.py "native store enterprise status"`
- `python src/main.py "native store enterprise signing set type=<kms|hsm> name=<provider> key=<ref> hsm=<on|off>"`
- `python src/main.py "native store enterprise vendor configure channel=<microsoft|apple|google_play|app_store_connect> identity=<id>"`
- `python src/main.py "native store enterprise backend set replicas=<n> tls=<on|off> monitoring=<on|off> alerting=<on|off> storage=<on|off> dr=<strategy>"`
- `python src/main.py "native store enterprise desktop set binary=<on|off> updater=<on|off> service=<on|off> registration=<on|off> crash=<on|off>"`
- `python src/main.py "native store enterprise secrets set provider=<name> ca=<name> revocation=<on|off>"`
- `python src/main.py "native store enterprise governance set oncall=<a,b> approvers=<a,b> freeze=<on|off>"`
- `python src/main.py "native store enterprise deployed test target=<env> passed=<on|off>"`
- `python src/main.py "native store scaffold vendor app=<name> version=<v>"`
- `python src/main.py "native store scaffold services"`
- `python src/main.py "native store scaffold backend"`
- `python src/main.py "native store scaffold gui"`
- `python src/main.py "native store backend init"`
- `python src/main.py "native store backend status"`
- `python src/main.py "native store backend deploy scaffold"`
- `python src/main.py "native store backend backup [name=<name>]"`
- `python src/main.py "native store backend restore path=<backup_path>"`
- `python src/main.py "native store backend user create id=<id> email=<email> tier=<tier>"`
- `python src/main.py "native store backend charge id=<charge_id> user=<user_id> amount=<n> currency=<code>"`
- `python src/main.py "native store backend event kind=<name> json=<json>"`
- `python src/main.py "native store desktop scaffold"`
- `python src/main.py "native store desktop launch"`
- `python src/main.py "native store build windows app=<name> version=<v>"`
- `python src/main.py "native store build linux app=<name> version=<v>"`
- `python src/main.py "native store build macos app=<name> version=<v> [signer=<identity>]"`
- `python src/main.py "native store build mobile app=<name> version=<v>"`
- `python src/main.py "native store artifact sign path=<artifact_path> signer=<name>"`
- `python src/main.py "native store artifact verify path=<artifact_path>"`
- `python src/main.py "native store e2e run app=<name> version=<v> traffic=<n> abuse=<n> failures=<n>"`
- `python src/main.py "native store pipeline run app=<name> os=<windows|linux|macos|android|ios> [format=<...>]"`
- `python src/main.py "native store install app=<name> [os=<target_os>]"`
- `python src/main.py "native store upgrade id=<install_id> version=<v>"`
- `python src/main.py "native store uninstall id=<install_id>"`
- `python src/main.py "native store service set os=<windows|linux|macos|android|ios> enabled=<on|off>"`
- `python src/main.py "native store trust channel set name=<stable|beta> signed=<on|off> notarization=<on|off>"`
- `python src/main.py "native store notarize app=<name> version=<v> signer=<id>"`
- `python src/main.py "native store backend integrate component=<identity|payments|fraud|cdn|compliance|legal_ops> provider=<name> enabled=<on|off>"`
- `python src/main.py "native store gui set [first_run=<on|off>] [deep=<on|off>]"`
- `python src/main.py "native store maximize"`

## Notes
- Uses published package artifacts from the universal store registry.
- Performs OS-targeted artifact copy/install tracking under `.zero_os/native_store/`.
- Adds per-OS package pipeline metadata for `msix/msi`, `deb/rpm`, `pkg/app`, `apk`, `ipa`.
- Tracks privileged installer service/daemon state, trust/notarization channels, backend integrations, and native GUI UX toggles.
- Generates production scaffold files under `build/native_store_prod/` for vendor packaging, service manifests, backend APIs, and a native client shell.
- Backend persistence is implemented with SQLite in `.zero_os/native_store/backend.db`.
- Backend deployment scaffolds are emitted under `build/native_store_prod/backend_deploy/`.
- Local artifact signing uses SHA-256 signature metadata sidecars for CI-verifiable integrity checks.
- End-to-end runtime ecosystem smoke reports are emitted under `.zero_os/native_store/ops/`.
- Enterprise external-provider readiness is tracked in `.zero_os/native_store/enterprise_ops.json` so vendor, backend, secrets, governance, and deployed-test gates can be evaluated together.
- Windows and Linux build commands invoke vendor tooling when available and return `missing_tools` when the host lacks the required toolchain.
- `native store status` now reports Windows and Linux packaging toolchain readiness so missing vendor binaries are visible at startup/runtime.
