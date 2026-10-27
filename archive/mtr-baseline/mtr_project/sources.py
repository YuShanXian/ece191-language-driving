"""Resolve exact scenario provenance; never choose the first available DB."""
from pathlib import Path
from .paths import ROOT

def source_database(conversion, root=ROOT):
    if conversion.get('source_db'):
        value=Path(conversion['source_db'])
        path=value if value.is_absolute() else root/value
    else:
        name=conversion.get('scenario','');prefix='sd_nuplan_v1_'
        if not name.startswith(prefix) or '_gps' not in name:
            raise ValueError('Scenario has no unambiguous source database provenance')
        clip=name[len(prefix):].rsplit('_gps',1)[0]
        if '/' in clip or '\\' in clip or '..' in clip:raise ValueError('Invalid clip ID')
        path=root/'data/nuplan/db'/f'{clip}.db'
    path=path.resolve()
    if not path.is_file():raise FileNotFoundError(path)
    return path
