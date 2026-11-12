"""Create a Finder-launchable bootstrap bundle, NOT a standalone native binary."""
from pathlib import Path
import plistlib
import shutil
from zipfile import ZipFile, ZIP_DEFLATED
root=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(root))
from sneg import __version__
base=root/'dist'/'mac-easy'
app=base/'Снег.app'
contents=app/'Contents'
(contents/'MacOS').mkdir(parents=True,exist_ok=True)
resources=contents/'Resources'
resources.mkdir(exist_ok=True)
for name in ('main.py','requirements.txt'):
    shutil.copy2(root/name,resources/name)
shutil.copytree(root/'sneg',resources/'sneg',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
shutil.copy2(root/'packaging'/'mac-launcher.sh',contents/'MacOS'/'Sneg')
(contents/'MacOS'/'Sneg').chmod(0o755)
with (contents/'Info.plist').open('wb') as f:
    plistlib.dump({'CFBundleName':'Снег','CFBundleDisplayName':'Снег',
        'CFBundleIdentifier':'app.sneg.easy','CFBundleExecutable':'Sneg',
        'CFBundlePackageType':'APPL','CFBundleVersion':__version__,'CFBundleShortVersionString':__version__,
        'LSMinimumSystemVersion':'12.0','NSHighResolutionCapable':True},f)
(base/'Начать здесь.txt').write_text('СНЕГ — С АВТООБНОВЛЕНИЕМ\n\nОдин раз завершите старую версию, замените Снег.app и откройте новый.\nДалее приложение проверяет GitHub при запуске и каждые 6 часов.\nКнопка «Обновить» скачает версию и перезапустит приложение.\nРаспаковывать следующие правки вручную не нужно.\n\nКод и версии: https://github.com/Belane360/sneg-desktop\nНастройки и уже установленные компоненты сохраняются.\nНа новом компьютере нужен Python 3.9–3.13 и интернет при первом запуске.\nПриложение пока не подписано Apple Developer ID.\n',encoding='utf-8')
with ZipFile(root/'dist'/f'Sneg-Mac-{__version__}.zip','w',ZIP_DEFLATED) as z:
    for path in base.rglob('*'):
        if path.is_file():
            # Public-readable archive entries, preserving the executable launcher.
            from zipfile import ZipInfo
            info=ZipInfo(str(path.relative_to(base)))
            info.create_system=3
            info.external_attr=(0o100755 if path.name=='Sneg' else 0o100644)<<16
            z.writestr(info,path.read_bytes(),compress_type=ZIP_DEFLATED)
print(root/'dist'/f'Sneg-Mac-{__version__}.zip')
