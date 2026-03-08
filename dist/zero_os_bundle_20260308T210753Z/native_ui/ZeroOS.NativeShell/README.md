# ZeroOS.NativeShell

Windows-native scaffold for a more production-grade Zero OS desktop application.

Current state:
- WPF desktop shell builds successfully
- branded main window
- tabbed desktop layout
- working buttons for clone/release/open actions
- working command execution for:
  - `zero os export bundle`
  - `zero os share package`
  - `core status`
  - `github status`
- artifact list and detail panel for bundle outputs
- package manifest scaffold added
- Windows CI workflow added for build/publish artifact output

Publish:
```powershell
.\publish.ps1
```

MSIX scaffold:
```powershell
.\package_msix.ps1
```

GitHub Actions:
- `.github/workflows/native-shell-windows.yml`
- builds the WPF app
- publishes the Windows app artifact
- uploads a release zip on version tags

Next steps:
- add richer tabbed navigation and release workflows
- add signing, installer, and auto-update flow
- package with MSIX or MSI
