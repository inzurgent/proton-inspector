# Third-party dependencies

The MIT license in `LICENSE` applies to Proton Inspector's application source.
Third-party dependencies retain their own licenses.

## PySide6, Shiboken6 and Qt

Proton Inspector imports QtCore and QtWidgets through PySide6. The launcher
installs PySide6 and its dependencies into a local virtual environment using
pip; those packages are not included in this source archive.

Qt for Python is offered under LGPLv3/GPLv3 and commercial licensing options.
Refer to the installed distributions' license files for the exact terms and
third-party notices applicable to the version you distribute. The MIT license
for this application does not relicense Qt or PySide6.

- Project and licensing: https://doc.qt.io/qtforpython-6/
- Licensing details: https://doc.qt.io/qtforpython-6/commercial/index.html
- Package metadata: https://pypi.org/project/PySide6/
- Source: https://code.qt.io/pyside/pyside-setup.git/

If distributing a bundled executable or an archive containing Qt/PySide6,
review the applicable redistribution requirements and include the necessary
license texts, notices and source/relinking arrangements. This repository is
a source distribution, not a bundled binary release.

## AppImage v0.1.0 distribution

Unlike the source archive, the AppImage bundles unmodified upstream dependency
binaries. The application remains MIT licensed. Qt/PySide6/Shiboken6 are used
under their LGPLv3 option, and retain their own copyrights. Full LGPLv3 and
GPLv3 texts are included at `usr/share/proton-inspector/licenses`.

Corresponding source code, including upstream build instructions, is available
without charge at the following locations (the exact distributed versions):

- [Qt 6.8.3 complete source archive](https://download.qt.io/archive/qt/6.8/6.8.3/single/qt-everywhere-src-6.8.3.tar.xz).
- [PySide6 and Shiboken6 6.8.3 source archive](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.8.3-src/pyside-setup-everywhere-src-6.8.3.tar.xz).
- [CPython 3.12.15 source](https://www.python.org/ftp/python/3.12.15/Python-3.12.15.tar.xz), under the PSF license and included third-party licenses; the runtime retains `opt/python3.12/lib/python3.12/LICENSE.txt`.
- [Python AppImage build recipes](https://github.com/niess/python-appimage) and [manylinux runtime builds](https://github.com/pypa/manylinux).
- [AppImage type-2 runtime source](https://github.com/AppImage/type2-runtime), under MIT; binary SHA-256 and download URL are recorded in the build script.

The bundled X11 helpers come from Debian bookworm: libxkbcommon 1.5.0,
xcb-util 0.4.0, xcb-util-cursor 0.1.4, xcb-util-image 0.4.0,
xcb-util-keysyms 0.4.0, xcb-util-renderutil 0.3.9 and xcb-util-wm 0.4.1.
Their copyright and license notices are retained under `usr/share/doc`.
Exact package versions and hashes appear in `packaging/debian-lock.json`.
Python packaging dependencies retain their distribution metadata and notices.
Qt's complete source archive includes the notices and source for its embedded
third-party components.

The bundled libraries can be inspected, modified and replaced by extracting
the AppImage; see [the packaging guide](packaging/README.md). AppImage build
utilities are build-time tools, not application code relicensed under MIT.
