# AppImage build

This recipe produces the experimental x86-64 release for Bazzite/Linux desktop.
It bundles CPython 3.12.15, PySide6-Essentials/Shiboken6 6.8.3 and X11 helper
libraries. It requires a recent Linux desktop (glibc 2.28 or newer; host graphics,
Wayland/X11 and system libraries are still required). Bazzite is the initial
target; this is not a promise of compatibility with every Linux distribution.

## Build

Requires x86-64 Linux, Python 3.12+ (for safe tar extraction), `bash`, `readlink`,
`file`, and internet access. FUSE, a compiler and root access are not required.

```bash
python3 packaging/build_appimage.py
QT_QPA_PLATFORM=offscreen dist/Proton-Inspector-0.1.2-x86_64.AppImage --appimage-extract-and-run --self-test
```

Use `--work-dir PATH` and `--output-dir PATH` to change build locations.
Downloads of the Python runtime, AppImage tools/runtime and Debian libraries
are checked against pinned SHA-256 hashes. PySide6 dependencies are version
pinned. The upstream AppImage tools use rolling URLs: a checksum mismatch
requires reviewing the new upstream binary before updating its recorded hash.
Do not disable the verification. Existing downloaded inputs are reused.

This is a repeatable recipe, not a claim of bit-for-bit reproducible output.

## Runtime and troubleshooting

```bash
chmod +x Proton-Inspector-0.1.2-x86_64.AppImage
./Proton-Inspector-0.1.2-x86_64.AppImage
```

If FUSE mounting is unavailable, use `--appimage-extract-and-run`. Alternatively:

```bash
./Proton-Inspector-0.1.2-x86_64.AppImage --appimage-extract
./squashfs-root/AppRun
```

No pip installation or network access is required to launch the built image.
The image does not change process inspection permissions. Linux ptrace/Yama
restrictions still apply. Offscreen self-tests verify the bundled Qt GUI and
memory engine, but do not verify the host compositor or a real game.

## Modifying bundled libraries

The AppImage is an extractable filesystem, with ordinary Python source and
shared Qt/PySide6 libraries. After extracting it, replace compatible libraries
under `opt/python3.12/lib/python3.12/site-packages` and launch `AppRun`. You can
also modify the build recipe and rebuild it. No signatures or activation checks
prevent modified versions from running. Reverse engineering for debugging
modifications to LGPL-covered components is permitted under their licenses.

See [third-party notices](../THIRD_PARTY_NOTICES.md) for licenses, source access
and build references. Licenses are also included inside the image under
`usr/share/proton-inspector/licenses` and the original dependency locations.
