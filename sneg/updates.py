"""GitHub Releases updates for the Python bootstrap distribution."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from zipfile import ZipFile
from . import __version__

REPOSITORY = 'Belane360/sneg-desktop'
ASSET = 'Sneg-update.zip'
MAX_DOWNLOAD = 8 * 1024 * 1024


def version_tuple(value):
    if not re.fullmatch(r'\d+\.\d+\.\d+',value):
        raise ValueError('Неподдерживаемый номер версии')
    return tuple(map(int,value.split('.')))


def update_root():
    if sys.platform=='darwin': base=Path.home()/'Library/Application Support'
    elif sys.platform=='win32': base=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))
    else: base=Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))
    return base/'Sneg/updates'


def atomic_json(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data),encoding='utf-8')
    os.replace(temporary,path)


def download(url,limit=MAX_DOWNLOAD):
    parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.netloc not in ('api.github.com','github.com'):
        raise ValueError('Недоверенный адрес обновления')
    if parsed.netloc=='github.com' and not parsed.path.startswith('/'+REPOSITORY+'/releases/download/'):
        raise ValueError('Обновление из другого репозитория')
    request=Request(url,headers={'User-Agent':'Sneg/'+__version__,'Accept':'application/vnd.github+json' if parsed.netloc=='api.github.com' else 'application/octet-stream'})
    with urlopen(request,timeout=25) as response:
        result=response.read(limit+1)
    if len(result)>limit: raise ValueError('Слишком большой файл обновления')
    return result


def latest_release():
    from urllib.error import HTTPError
    try: data=json.loads(download(f'https://api.github.com/repos/{REPOSITORY}/releases/latest',1024*1024))
    except HTTPError as error:
        if error.code==404:return None
        raise
    version=data['tag_name'].removeprefix('v')
    version_tuple(version)
    if data.get('draft') or data.get('prerelease') or version_tuple(version)<=version_tuple(__version__):return None
    assets={a['name']:a['browser_download_url'] for a in data.get('assets',[])}
    if ASSET not in assets or ASSET+'.sha256' not in assets:return None
    return {'version':version,'url':assets[ASSET],'checksum_url':assets[ASSET+'.sha256']}


def safe_extract(payload,destination):
    import io
    with ZipFile(io.BytesIO(payload)) as archive:
        seen=set();total=0
        for item in archive.infolist():
            path=PurePosixPath(item.filename)
            if item.is_dir():continue
            allowed=(item.filename in ('main.py','requirements.txt') or
                     (len(path.parts)==2 and path.parts[0]=='sneg' and path.suffix=='.py'))
            if (not allowed or path.is_absolute() or '..' in path.parts or '\\' in item.filename
                or item.filename in seen or ((item.external_attr>>16)&0o170000)==0o120000):
                raise ValueError('Недопустимый файл в обновлении')
            seen.add(item.filename);total+=item.file_size
            if total>MAX_DOWNLOAD:raise ValueError('Слишком большой распакованный архив')
        if not {'main.py','requirements.txt','sneg/__init__.py','sneg/app.py'}.issubset(seen):
            raise ValueError('Неполное обновление')
        archive.extractall(destination)


def prepare_update(release, root=None):
    """Verify and stage before changing the active version."""
    root=root or update_root()
    version=release['version'];version_tuple(version)
    if version_tuple(version)<=version_tuple(__version__):raise ValueError('Версия уже установлена')
    digest=download(release['checksum_url'],1024).decode('ascii').split()[0]
    if not re.fullmatch('[0-9a-fA-F]{64}',digest):raise ValueError('Некорректная контрольная сумма')
    payload=download(release['url'])
    if hashlib.sha256(payload).hexdigest()!=digest.lower():raise ValueError('Контрольная сумма не совпала')
    root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root,prefix='staging-') as temp:
        stage=Path(temp);safe_extract(payload,stage)
        installed_requirements=(Path(__file__).resolve().parents[1]/'requirements.txt').read_bytes()
        if (stage/'requirements.txt').read_bytes()!=installed_requirements:
            raise ValueError('Эта версия меняет компоненты. Требуется полная установка из GitHub Releases.')
        # Import Qt and the new app in an isolated process before activating it.
        probe='from sneg import __version__; from sneg.app import main; assert __version__ == '+repr(version)
        subprocess.run([sys.executable,'-c',probe],cwd=stage,check=True,timeout=30,
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        destination=root/'versions'/version
        destination.parent.mkdir(exist_ok=True)
        if destination.exists():shutil.rmtree(destination)
        shutil.move(str(stage),str(destination))
    return version


def activate(version,root=None):
    root=root or update_root();version_tuple(version)
    if not (root/'versions'/version/'sneg/app.py').is_file():raise ValueError('Версия не подготовлена')
    path=root/'active.json'
    previous=json.loads(path.read_text()).get('version') if path.exists() else None
    atomic_json(path,{'version':version,'previous':previous})


def bootstrap_entry():
    return Path(os.environ.get('SNEG_BOOTSTRAP_ENTRY',Path(__file__).resolve().parents[1]/'main.py'))
