#!/usr/bin/env python3
"""Build on x86-64 Linux; no compiler, root, FUSE or system Python modules needed."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.1.4.1'
DOWNLOADS = {
    'python.AppImage': ('https://github.com/niess/python-appimage/releases/download/python3.12/python3.12.15-cp312-cp312-manylinux2014_x86_64.AppImage', 'a6a9bf619a3e21c5623be144d8ac4e458e1a5b5c133b1cc99b142d6e71b82c76'),
    'appimagetool.AppImage': ('https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage', 'e8c1169c4af66c3184d7ee110713d4be04befe671fa358e2c1591ee840553b03'),
    'runtime-x86_64': ('https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64', '617aa77314d57c8b8e4fae9c3f0b35af7b30d5529cb69e98f64f92510ed98a46'),
}

def download(url, path, digest=None):
    if not path.exists():
        print(f'Downloading {path.name}', flush=True)
        with urllib.request.urlopen(url) as response, path.open('wb') as output:
            shutil.copyfileobj(response, output)
    if digest and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise RuntimeError(f'Checksum mismatch for {path}; upstream may have replaced a rolling asset. Review and update the pinned checksum explicitly.')

def extract_appimage(path, destination):
    if destination.exists(): return
    path.chmod(0o755)
    with (path.parent/(path.stem+'-extract.log')).open('w') as log:
        subprocess.run([str(path),'--appimage-extract'],cwd=path.parent,stdout=log,check=True)
    (path.parent/'squashfs-root').rename(destination)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--work-dir',type=Path,default=ROOT/'build'/'appimage')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'dist')
    args=parser.parse_args()
    if platform.machine() != 'x86_64': raise SystemExit('This recipe currently builds x86-64 only.')
    work=args.work_dir.resolve(); output=args.output_dir.resolve()
    work.mkdir(parents=True,exist_ok=True); output.mkdir(parents=True,exist_ok=True)
    for name,(url,digest) in DOWNLOADS.items(): download(url,work/name,digest)
    appdir=work/'ProtonInspector.AppDir'
    extract_appimage(work/'python.AppImage',appdir)
    extract_appimage(work/'appimagetool.AppImage',work/'appimagetool.AppDir')
    python=appdir/'opt/python3.12/bin/python3.12'
    subprocess.run([str(python),'-m','pip','install','PySide6-Essentials==6.8.3','numpy==2.5.5','dnfile==0.18.0','dncil==1.0.2','pefile==2024.8.26'],check=True)
    # Include the X11 helper libraries and their Debian copyright notices.
    for package in json.loads((ROOT/'packaging/debian-lock.json').read_text()):
        archive=work/Path(package['Filename']).name
        download('https://deb.debian.org/debian/'+package['Filename'],archive,package['SHA256'])
        data=archive.read_bytes()
        if data[:8]!=b'!<arch>\n': raise RuntimeError('Invalid deb archive')
        offset=8
        while offset<len(data):
            header=data[offset:offset+60]; size=int(header[48:58]); name=header[:16].decode().strip().rstrip('/')
            payload=data[offset+60:offset+60+size]
            if name.startswith('data.tar'):
                with tarfile.open(fileobj=io.BytesIO(payload),mode='r:*') as tar:
                    tar.extractall(appdir,filter='data')
                break
            offset+=60+size+(size%2)
    # Replace Python's desktop launcher while keeping the bundled runtime intact.
    for path in [appdir/'AppRun',appdir/'.DirIcon',appdir/'python.png',*appdir.glob('python*.desktop')]:
        if path.is_symlink() or path.exists(): path.unlink()
    for name in ['AppRun','proton-inspector.desktop','proton-inspector.svg']:
        shutil.copy2(ROOT/'packaging'/name,appdir/name)
    (appdir/'AppRun').chmod(0o755)
    (appdir/'.DirIcon').symlink_to('proton-inspector.svg')
    source=appdir/'usr/share/proton-inspector'
    if source.exists(): shutil.rmtree(source)
    source.mkdir(parents=True)
    for path in ROOT.iterdir():
        if path.is_file() and (path.suffix in ('.py','.md','.txt') or path.name=='LICENSE'):
            shutil.copy2(path,source/path.name)
    shutil.copytree(ROOT/'packaging',source/'packaging',ignore=shutil.ignore_patterns('__pycache__','flatpak'))
    # Preserve upstream licenses and add the full LGPL/GPL texts beside the source.
    licenses=source/'licenses'; licenses.mkdir(exist_ok=True)
    for name in ('LGPL-3.0-only.txt','GPL-3.0-only.txt'):
        download('https://raw.githubusercontent.com/qt/qtbase/v6.8.3/LICENSES/'+name,licenses/name)
    subprocess.run(['chmod','-R','a+rX',str(appdir)],check=True)
    env=dict(os.environ,ARCH='x86_64',VERSION=VERSION)
    target=output/f'Proton-Inspector-{VERSION}-x86_64.AppImage'
    subprocess.run([str(work/'appimagetool.AppDir/AppRun'),'--no-appstream','--runtime-file',str(work/'runtime-x86_64'),str(appdir),str(target)],env=env,check=True)
    print(f'Built {target}',flush=True)

if __name__=='__main__': main()
