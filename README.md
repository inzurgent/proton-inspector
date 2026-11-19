# Proton Inspector

A lightweight Linux desktop memory scanner and editor for games running through Wine/Proton. Built with Python and PySide6, with a workflow inspired by Cheat Engine.

**Status:** early prototype. Basic operation has been reported working by the maintainer on Bazzite with **Probably Stolen**. Compatibility with other games and Linux configurations is not yet established. This is an independent project, not affiliated with Cheat Engine, Valve, or the Proton project.

## Features

- Search running processes by name, command, or PID.
- Scan all supported numeric types together, or choose one integer or floating-point type.
- Narrow matches by exact value, changed, unchanged, increased, or decreased.
- Edit values and freeze addresses with repeated writes.
- Keep named addresses in a separate tab and save/load JSON lists.
- Try the workflow using an included demo process.

## Releases and AppImage download

Download the **x86-64 AppImage** from [GitHub Releases](https://github.com/inzurgent/proton-inspector/releases).
The first packaged release is **v0.1.0**, an experimental Linux desktop build.
Python and Qt are included; no pip installation is needed.

```bash
chmod +x Proton-Inspector-0.1.0-x86_64.AppImage
./Proton-Inspector-0.1.0-x86_64.AppImage
```

If your system cannot mount AppImages through FUSE:

```bash
./Proton-Inspector-0.1.0-x86_64.AppImage --appimage-extract-and-run
```

A `SHA256SUMS` file accompanies the release. Run `sha256sum -c SHA256SUMS`
in the directory containing the downloaded assets to verify them. The image
uses the same Linux process permissions as the source version. See the
[packaging guide](packaging/README.md) for build instructions, extraction,
library replacement and platform limitations.

## Requirements (running from source)

- Linux desktop with Python 3, `venv`, and `pip`.
- A Python version supported by the PySide6 wheel available for your platform.
- A graphical session and the system libraries required by Qt.
- Permission to inspect the target process.
- Internet access for the first dependency installation.

## Run on Bazzite

Extract/copy this folder somewhere writable. Run on the Bazzite host, alongside Steam:

```bash
bash run.sh
```

Requires Python 3 with venv/pip, internet for first-time dependency installation, and a graphical desktop. The launcher installs PySide6 in the local `.venv`; it does not modify the base OS. The maintainer has reported a working Bazzite setup; automatic installation of missing host prerequisites is not included. A Flatpak/container deployment is not provided: process visibility and memory access across sandbox boundaries require additional integration.

## Try the demo

1. Click **Start demo**. This creates a child process with an int32 value of `123456789` and displays its exact address.
2. Click **New scan**. Find the address shown in the demo status message among the matches.
3. Select that address, enter `77` in the bottom field, then **Write value** or **Freeze value**.
4. Set the scan value to `77` and click **Next scan** with `exact`, or choose `changed` / `decreased` to narrow the prior results.
5. **Unfreeze all** stops repeated writes. Closing the app stops its demo process.

Results show the last scan baseline, not live values. Writes intentionally preserve that baseline for change comparisons. A completed scan clears freezes. Freeze repeats writes about every 150 ms.

## Try a game

Launch the game normally and refresh the process list. Use the search box to filter instantly by name, command, or PID (for example, `stolen`). Search is case-insensitive; multiple words must all match. Clear the search to show all processes. Select the game’s actual `.exe` process rather than Steam or wineserver. Attach, choose the numeric type, and search a known value. Change it in the game and use **Next scan** to narrow matches. A new scan always uses exact matching, regardless of the refinement dropdown.

Linux permission checks apply even for same-user processes. Read-only diagnostics:

```bash
cat /proc/sys/kernel/yama/ptrace_scope
```

Yama mode 1 commonly prevents attaching to an independently launched game; the child-process demo can still work. Other access controls can also deny access. This prototype reports the denial and does not change permissions. A scoped game-launch/privileged-helper integration is still needed for those configurations. Do not run the whole GUI as root or grant capabilities to a general-purpose Python interpreter.

## Scan all numeric types

Choose **All numeric types** (the default) to search `int32`, `uint32`, `int64`,
`float32`, and `float64` in one pass. The results table shows the type of each
match. A location may appear more than once when its bytes match multiple
types, such as signed and unsigned integers.

Enter a known number, run **New scan**, change the value in the game, then use
**Next scan** to narrow the results. Each result retains its numeric type for
refinement, editing, freezing and saving. The type selector applies to new
scans; changing it does not reinterpret existing results.

Inputs that cannot be encoded in a particular type skip that type in combined
scans. For example, `1.5` searches floating-point types; out-of-range integers
are skipped for integer types that cannot hold them. Invalid input leaves prior
results intact. “All” covers the five supported numeric types, not text, byte
patterns, or unknown initial values. Choose a single type to reduce ambiguous
matches. Float searches still compare the exact encoded value.

## Saved addresses

Select one or more scan results and click **Add selected to saved addresses**, or double-click a result. The **Saved addresses** tab keeps the list independent of later scans. Select an entry and click **Rename** to label it (for example, Money or Health).

Use **Refresh values** to read current values. The shared **Write value** and **Freeze value** buttons act on the selected entry in the active tab, using that entry’s saved numeric type. **Remove selected** also stops freezing the removed addresses.

**Save list…** writes names, hexadecimal addresses and numeric types to a JSON file. **Load list…** restores that list; loading replaces an existing list after confirmation and turns all freezes off. It does not attach to a process or write values. Unsaved changes are not automatically saved when the app closes.

Addresses are absolute, not pointers: restarting the game or changing scenes may invalidate them or reuse the same location for something else. Verify them before editing. Saved lists do not resolve addresses across restarts. Values refresh on tab selection, list edits, or **Refresh values**, not continuously.

## Scope and limitations

- Signed 32/64-bit integers, unsigned 32-bit integers, float32/64.
- Exact first scan; exact, changed, unchanged, increased and decreased refinement.
- Naturally aligned values in readable/writable mappings only. Floating point exact searches compare encoded bytes.
- First scans run in a background thread with cancellation; partial results are discarded on cancellation.
- Up to 250,000 candidates; first 2,000 displayed. No unknown-initial-value scanning.
- Unreadable chunks are skipped and counted. A skipped chunk may contain valid candidates; scans are not atomic snapshots of a running game.
- No pointer scanner, overlay, disassembler, scripting, Cheat Engine table import, or anti-cheat integration.
- Freezes are temporary address writes; they cannot track an allocation that moves or is reused inside the same process.
- Python scanning is a prototype implementation and may be slow on large games.

## Verification

```bash
python3 -m unittest discover -s . -v
```

Verified in a Fedora 44 container: cross-process reads/writes, exact scans, refinement, cancellation, numeric encodings and process-identity protection. Qt offscreen smoke test covered window creation, demo attachment, editing, freezing, unfreezing and cleanup. The maintainer separately reported successful basic use on Bazzite with Probably Stolen. This is not a comprehensive game compatibility test. Saved-address file validation and round-trip tests are included; the saved-address Qt workflow was also smoke-tested offscreen.

References: [Linux process_vm_readv](https://man7.org/linux/man-pages/man2/process_vm_readv.2.html), [Yama permissions](https://kernel.org/doc/html/v5.16/admin-guide/LSM/Yama.html), [Bazzite software installation](https://docs.bazzite.gg/Installing_and_Managing_Software/).


## Contributing

Bug reports and pull requests are welcome. For bugs, include your distribution,
Python and PySide6 versions, Proton version, game name, the operation that failed,
and the error text. Include a minimal reproduction with the demo process when possible.

Before submitting changes, run the tests in the Verification section. Keep local
virtual environments, caches, and personal address lists out of commits.

## License

[MIT](LICENSE) — Copyright (c) 2026 inzurgent.

PySide6, Qt, and other dependencies retain their own licenses; see
[Third-party notices](THIRD_PARTY_NOTICES.md). The source archive does not bundle
those dependencies.
