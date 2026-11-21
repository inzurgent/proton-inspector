# Flatpak package

This is a **Flatpak host launcher**, not a sandboxed memory scanner. Flatpak's
process isolation prevents an ordinary sandboxed app from finding and modifying
host game processes. The launcher therefore runs the bundled, verified v0.1.3
AppImage on the host using `flatpak-spawn --host`.

## Install and run

Download `Proton-Inspector-0.1.3-x86_64.flatpak` from [Releases](https://github.com/inzurgent/proton-inspector/releases/tag/v0.1.3), then:

```bash
flatpak install --user ./Proton-Inspector-0.1.3-x86_64.flatpak
flatpak run io.github.inzurgent.ProtonInspector
```

Alternatively open the bundle in a Flatpak-capable software manager, then launch
**Proton Inspector** from the desktop app menu. Flatpak may download the
Freedesktop 25.08 runtime if it is not already installed. Python and Qt are
included in the package. AppImage extraction is automatic; FUSE is not needed.

This is a standalone, unsigned experimental bundle, not a Flathub listing.
Future updates require installing a newer bundle from Releases; there is no
application update remote. The runtime still receives its normal remote updates.

## Permissions

The package requests `--talk-name=org.freedesktop.Flatpak`, which allows host
command execution. The scanner runs **outside Flatpak's sandbox** with your
normal user privileges and can access your files and processes, just like the
AppImage. It does not elevate privileges or disable ptrace/Yama restrictions.
This permission is fundamental to this launcher; removing it prevents launch.
The launcher does not request blanket filesystem, network, device, or display
access for the sandbox itself, since the application runs on the host.

Address lists are saved to the host location you choose, not forcibly inside
Flatpak's private data directory. Saved addresses and all existing application
features behave as they do in the AppImage.

## Test

```bash
flatpak run io.github.inzurgent.ProtonInspector --self-test
```

This runs the bundled unit tests and offscreen Qt/demo test on the host. It does
not attach to or modify a running game. Real desktop and game testing is still
needed after installation on your system.

## Build

Requires x86-64 Linux, Python 3, Flatpak and the Freedesktop Platform 25.08 runtime
installed from Flathub. No SDK, compiler or flatpak-builder is required: the
payload is already built. Download the v0.1.3 AppImage from Releases first.

```bash
python3 packaging/flatpak/build_flatpak.py \
  --appimage /path/to/Proton-Inspector-0.1.3-x86_64.AppImage
```

The script checks the AppImage's pinned SHA-256, stages the launcher and metadata,
exports a local OSTree repository, and creates the `.flatpak` in `dist/`.
Use `--work-dir PATH --output-dir PATH` to choose other directories. Rebuilds
require a fresh work directory. The bundle includes the unchanged AppImage;
its MIT application license, dependency licenses and corresponding-source
links remain applicable. See [third-party notices](../../THIRD_PARTY_NOTICES.md).

## Uninstall

```bash
flatpak uninstall --user io.github.inzurgent.ProtonInspector
```

Host address-list files you saved are not removed by uninstalling the app.
