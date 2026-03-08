# Universal App Store (Multi-OS)

Zero OS now includes a neutral app-store distribution layer for multi-target packages.

## Package Layout
```text
app_package/
 ├── manifest.json
 ├── linux/app_binary
 ├── windows/app.exe
 ├── mac/app.app
 ├── android/app.apk
 └── ios/app.ipa
```

## Manifest
```json
{
  "name": "ExampleApp",
  "version": "1.0",
  "targets": {
    "windows": "windows/app.exe",
    "linux": "linux/app_binary",
    "macos": "mac/app.app",
    "android": "android/app.apk",
    "ios": "ios/app.ipa"
  }
}
```

## Commands
- `python src/main.py "store validate <package_dir>"`
- `python src/main.py "store publish <package_dir>"`
- `python src/main.py "store list"`
- `python src/main.py "store resolve <app_name> [os=<windows|linux|macos|android|ios>]"`
- `python src/main.py "store resolve device <app_name> [os=<...>] [cpu=<...>] [arch=<...>] [security=<...>]"`
- `python src/main.py "store client detect"`
- `python src/main.py "store security scan <app_name>"`

## Current Scope
- Multi-target manifest parsing and validation
- Registry indexing and publish flow
- OS target selection (auto-detect or explicit override)
- Per-target hash metadata
- UAP folder checks (`builds/`, `metadata/`, `signature/developer.sig`)
- Fallback resolution (`web.wasm` / compatibility runtime suggestion)

## Next Scope
- Signature verification for each target artifact
- CDN/object storage backend
- Client installer flow + rollback
