"""Record the working local runtime without changing installed packages."""
import json,platform,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from importlib import metadata
from mtr_project.paths import ROOT,sha256,write_json


def capture(command):
    return subprocess.run(command,cwd=ROOT,text=True,capture_output=True,check=True).stdout


def main():
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    dest=ROOT/'config/environment-snapshots'/stamp;dest.mkdir(parents=True,exist_ok=False)
    (dest/'pip-freeze.txt').write_text(capture([sys.executable,'-m','pip','freeze']),encoding='utf-8')
    (dest/'pip-check.txt').write_text(capture([sys.executable,'-m','pip','check']),encoding='utf-8')
    conda=capture(['/opt/ece191-mtr/bootstrap/bin/micromamba','env','export','--explicit','-p',sys.prefix])
    if '@EXPLICIT' not in conda:raise ValueError('Explicit environment export is incomplete')
    (dest/'conda-explicit.txt').write_text(conda,encoding='utf-8')
    repositories={}
    for relative in ['vendor/valeo4cast','vendor/valeo4cast/UniTraj','vendor/valeo4cast/scenarionet']:
        repo=ROOT/relative;head=capture(['git','-C',str(repo),'rev-parse','HEAD']).strip()
        diff=capture(['git','-C',str(repo),'diff','HEAD','--binary'])
        name=relative.replace('/','-')+'.patch';(dest/name).write_text(diff,encoding='utf-8')
        repositories[relative]={'commit':head,'working_tree_patch':name,'patch_sha256':sha256(dest/name)}
    import torch,imageio_ffmpeg
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    names=['torch','torchvision','numpy','nuplan-devkit','imageio-ffmpeg','geopandas','shapely','matplotlib','scenarionet','unitraj']
    summary={'created_utc':stamp,'python':sys.version,'prefix':sys.prefix,'platform':platform.platform(),
        'packages':{name:metadata.version(name) for name in names},'torch_cuda':torch.version.cuda,
        'cuda_available':torch.cuda.is_available(),'gpu':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        'nvcc':capture([str(Path(sys.prefix)/'bin/nvcc'),'--version']).strip(),
        'ffmpeg_version':capture([ffmpeg,'-version']).splitlines()[0],'ffmpeg_binary_sha256':sha256(ffmpeg),
        'repositories':repositories,'files':{p.name:sha256(p) for p in dest.iterdir() if p.is_file()},
        'scope':'Snapshot of working runtime; fresh-machine restore untested. Editable packages need source trees and patches. pip-freeze alone is not a complete installer.'}
    write_json(dest/'environment.json',summary)
    print(json.dumps({'snapshot':str(dest),'packages':summary['packages'],'gpu':summary['gpu'],'pip_check':(dest/'pip-check.txt').read_text().strip()},indent=2))


if __name__=='__main__':main()
