"""Stable launcher: select an update without replacing the installed .app bundle."""
import json
import os
from pathlib import Path
import sys


def run():
    entry=Path(__file__).resolve()
    os.environ['SNEG_BOOTSTRAP_ENTRY']=str(entry)
    from sneg import __version__ as bundled_version
    from sneg.updates import update_root,version_tuple,atomic_json
    root=update_root();state_file=root/'active.json';state={};target=None
    if state_file.exists():
        try:
            state=json.loads(state_file.read_text())
            version=state['version']
            if version_tuple(version)>version_tuple(bundled_version):
                candidate=root/'versions'/version
                if (candidate/'sneg/app.py').is_file():target=candidate
        except (ValueError,KeyError,TypeError):pass
    if target:
        # Remove bundled imports so every module comes from the same release.
        for key in list(sys.modules):
            if key=='sneg' or key.startswith('sneg.'):del sys.modules[key]
        sys.path.insert(0,str(target))
    try:
        from sneg.app import main
        result=main()
        if result and target:raise RuntimeError('Не удалось запустить обновление')
        return result
    except Exception:
        if not target:raise
        import traceback
        root.mkdir(parents=True,exist_ok=True)
        (root/'last-error.log').write_text(traceback.format_exc(),encoding='utf-8')
        previous=state.get('previous')
        if previous:
            try:version_tuple(previous)
            except (ValueError,TypeError):previous=None
        atomic_json(state_file,{'version':previous or bundled_version,'previous':None})
        os.execv(sys.executable,[sys.executable,str(entry),*sys.argv[1:]])


if __name__=='__main__':
    raise SystemExit(run())
