#!/usr/bin/env python3
"""Wrap the verified AppImage in a Flatpak desktop launcher."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess

APP_ID='io.github.inzurgent.ProtonInspector'
IMAGE='Proton-Inspector-0.1.4.1-x86_64.AppImage'
IMAGE_SHA256='71068e7625372ce14ecbc681b8dee36bfc1c9c45e86936c2dfe830dc8ea8749d'
HERE=Path(__file__).resolve().parent

def run(*args): subprocess.run([str(x) for x in args],check=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--appimage',type=Path,required=True)
    parser.add_argument('--work-dir',type=Path,default=HERE.parents[1]/'build/flatpak')
    parser.add_argument('--output-dir',type=Path,default=HERE.parents[1]/'dist')
    args=parser.parse_args()
    if hashlib.sha256(args.appimage.read_bytes()).hexdigest()!=IMAGE_SHA256:
        raise SystemExit('AppImage checksum differs from the verified v0.1.4.1 release. Review before updating the recipe.')
    work=args.work_dir.resolve(); output=args.output_dir.resolve()
    app=work/'app'; repo=work/'repo'
    work.mkdir(parents=True,exist_ok=True); output.mkdir(parents=True,exist_ok=True)
    if (app/'metadata').exists() and 'command=' in (app/'metadata').read_text():
        raise SystemExit('Build directory is already finalized; use a fresh --work-dir.')
    if not (app/'metadata').exists():
        run('flatpak','build-init',app,APP_ID,'org.freedesktop.Platform','org.freedesktop.Platform','25.08')
    files=app/'files'
    for folder in ['bin','lib/proton-inspector','share/applications','share/metainfo','share/icons/hicolor/scalable/apps','share/doc/'+APP_ID]:
        (files/folder).mkdir(parents=True,exist_ok=True)
    shutil.copy2(args.appimage,files/'lib/proton-inspector'/IMAGE)
    (files/'lib/proton-inspector'/IMAGE).chmod(0o755)
    shutil.copy2(HERE/'proton-inspector',files/'bin/proton-inspector')
    (files/'bin/proton-inspector').chmod(0o755)
    shutil.copy2(HERE/(APP_ID+'.desktop'),files/'share/applications'/(APP_ID+'.desktop'))
    shutil.copy2(HERE/(APP_ID+'.metainfo.xml'),files/'share/metainfo'/(APP_ID+'.metainfo.xml'))
    shutil.copy2(HERE.parent/'proton-inspector.svg',files/'share/icons/hicolor/scalable/apps'/(APP_ID+'.svg'))
    for source in [HERE/'README.md',HERE.parents[1]/'LICENSE',HERE.parents[1]/'THIRD_PARTY_NOTICES.md']:
        shutil.copy2(source,files/'share/doc'/APP_ID/source.name)
    run('flatpak','build-finish','--command=proton-inspector','--talk-name=org.freedesktop.Flatpak',app)
    run('flatpak','build-export',repo,app,'stable')
    target=output/'Proton-Inspector-0.1.4.1-x86_64.flatpak'
    run('flatpak','build-bundle',repo,target,APP_ID,'stable','--runtime-repo=https://flathub.org/repo/flathub.flatpakrepo')
    print(target)

if __name__=='__main__': main()
