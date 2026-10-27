"""Capture pinned official controller config and inspect DB state fields."""
import importlib.metadata
import json
import sqlite3
import urllib.request
from pathlib import Path
from mtr_project.paths import ROOT, sha256, write_json


def main():
    distribution=importlib.metadata.distribution('nuplan-devkit')
    direct=json.loads(distribution.read_text('direct_url.json'))
    commit=direct['vcs_info']['commit_id']
    url=f'https://api.github.com/repos/motional/nuplan-devkit/git/trees/{commit}?recursive=1'
    with urllib.request.urlopen(url,timeout=30) as response:body=response.read(4*1024*1024+1)
    if len(body)>4*1024*1024:raise ValueError('Source index exceeds bound')
    tree=json.loads(body)
    if tree.get('truncated'):raise ValueError('Truncated source tree')
    paths=[x['path'] for x in tree['tree'] if x['path'].endswith('.yaml') and ('lqr' in x['path'] or 'two_stage' in x['path'])]
    folder=ROOT/'config/controller-reference-v1';folder.mkdir(exist_ok=True)
    sources=[]
    for name in paths:
        address=f'https://raw.githubusercontent.com/motional/nuplan-devkit/{commit}/{name}'
        with urllib.request.urlopen(address,timeout=30) as response:data=response.read(65537)
        if len(data)>65536:raise ValueError('Config exceeds bound')
        path=folder/Path(name).name;path.write_bytes(data)
        sources.append({'url':address,'upstream_path':name,'file':str(path.relative_to(ROOT)),'sha256':sha256(path)})
        print(name+'\n'+data.decode(),flush=True)
    db=ROOT/'data/nuplan/db/2021.06.09.18.23.43_veh-35_00026_00274.db'
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as connection:
        columns=[r[1] for r in connection.execute('PRAGMA table_info(ego_pose)')]
    result={'installed_package':direct,'tree_url':url,'configs':sources,'ego_pose_columns':columns}
    write_json(folder/'source-receipt.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
