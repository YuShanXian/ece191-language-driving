#!/usr/bin/env bash
set -euo pipefail
MTR_ROOT=/opt/ece191-mtr
mkdir -p "$MTR_ROOT/bootstrap"
if [ ! -x "$MTR_ROOT/bootstrap/bin/micromamba" ]; then
  curl --fail --location --retry 2 https://micro.mamba.pm/api/micromamba/linux-64/latest -o "$MTR_ROOT/bootstrap/micromamba.tar.bz2"
  python3 - <<'PY'
import tarfile
from pathlib import Path
root = Path('/opt/ece191-mtr/bootstrap')
with tarfile.open(root / 'micromamba.tar.bz2') as archive:
    member = archive.getmember('bin/micromamba')
    assert member.isfile()
    archive.extract(member, root, filter='data')
PY
fi
"$MTR_ROOT/bootstrap/bin/micromamba" create -y -r "$MTR_ROOT/mamba" -p "$MTR_ROOT/env" --override-channels -c conda-forge -c nvidia python=3.10 pip 'setuptools<81' 'gxx_linux-64=12' ninja 'cuda-nvcc=12.8' 'cuda-cudart-dev=12.8' 'cuda-cccl=12.8'
