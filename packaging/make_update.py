"""Build the exact, small source payload used by the installed bootstrap app."""
from pathlib import Path
import hashlib
import sys
from zipfile import ZipFile,ZIP_DEFLATED
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from sneg import __version__
if len(sys.argv)>1 and sys.argv[1]!='v'+__version__:raise SystemExit('Tag and application version differ')
output=root/'dist';output.mkdir(exist_ok=True)
archive=output/'Sneg-update.zip'
files=[root/'main.py',root/'requirements.txt',*sorted((root/'sneg').glob('*.py'))]
with ZipFile(archive,'w',ZIP_DEFLATED) as z:
    for path in files:z.write(path,path.relative_to(root))
(archive.with_suffix('.zip.sha256')).write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
print(__version__,archive)
