# Zero OS Native Boot Media

This project now includes a minimal standalone native image path.

## What It Builds
- A BIOS bootable raw image (`.img`)
- Boot sector loads stage-2 from disk sectors and jumps
- Stage-2 prints `Zero OS Stage2 loaded`, loads kernel payload, then switches to protected mode
- Kernel entry (`kmain`) installs IDT, remaps PIC, configures PIT timer IRQ stub
- Kernel scaffold now includes paging, user/kernel segment model, syscall gate, scheduler hooks, and phys/virt alloc primitives
- Artifact path: `build/native_os/zero_os_native.img`

## Prerequisites (Windows)
- NASM
- QEMU (`qemu-system-i386`)

Example install:
- `winget install NASM.NASM`
- `winget install SoftwareFreedomConservancy.QEMU`

## Build
- `.\zero_os_launcher.ps1 native-build`
- Full native build system (kernel + userland + manifest):
  - `.\zero_os_launcher.ps1 native-build-all`

Custom image:
- `.\zero_os_launcher.ps1 native-build:zero_os_native.img,1440`

## Run
- `.\zero_os_launcher.ps1 native-run`

Custom path:
- `.\zero_os_launcher.ps1 native-run:.\build\native_os\zero_os_native.img`

## Developer Ecosystem
- Toolchain status:
  - `.\zero_os_launcher.ps1 native-toolchain`
- QEMU integration smoke:
  - `.\zero_os_launcher.ps1 native-smoke`
- Build manifest output:
  - `build/native_os/build_manifest.json`

## Notes
- This now includes stage-2 + protected-mode handoff skeleton.
- Includes 32-bit kernel entry with IRQ0 timer handler prototype.
- Includes multi-sector stage2 kernel loader (CHS loop) for larger kernel payloads.
- Next step is real ring3 task launch, per-process page directories, and full context save/restore.
