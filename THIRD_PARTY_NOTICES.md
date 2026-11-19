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
