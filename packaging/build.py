"""Run on target OS: python packaging/build.py"""
from pathlib import Path
import platform
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed','--name','Sneg',
      '--paths',str(root),'--exclude-module','PySide6.QtWebEngineCore',
      '--exclude-module','PySide6.QtQml','--exclude-module','PySide6.QtQuick']
if sys.platform == 'darwin':
    args += ['--osx-bundle-identifier','app.sneg.desktop']
args += [str(root/'main.py')]
subprocess.run(args,cwd=root,check=True)
if sys.platform == 'darwin':
    staging=root/'build'/'dmg'
    staging.mkdir(exist_ok=True)
    import shutil
    shutil.copytree(root/'dist'/'Sneg.app',staging/'Sneg.app',dirs_exist_ok=True)
    link=staging/'Applications'
    if not link.exists(): link.symlink_to('/Applications')
    subprocess.run(['hdiutil','create','-volname','Sneg','-srcfolder',str(staging),'-ov','-format','UDZO',str(root/'dist'/f'Sneg-macOS-{platform.machine()}.dmg')],check=True)
