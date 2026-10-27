#!/usr/bin/env bash
set -euo pipefail
MTR_PREP=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
MTR_ENV=/opt/ece191-mtr/env
export PATH="$MTR_ENV/bin:$PATH"
export CUDA_HOME="$MTR_ENV"
export CPATH="$MTR_ENV/targets/x86_64-linux/include${CPATH:+:$CPATH}"
export LIBRARY_PATH="$MTR_ENV/targets/x86_64-linux/lib${LIBRARY_PATH:+:$LIBRARY_PATH}"
for cuda_include in "$MTR_ENV"/lib/python3.10/site-packages/nvidia/*/include; do
  export CPATH="$CPATH:$cuda_include"
done
export CC="$MTR_ENV/bin/x86_64-conda-linux-gnu-cc"
export CXX="$MTR_ENV/bin/x86_64-conda-linux-gnu-c++"
export TORCH_CUDA_ARCH_LIST=12.0
export MAX_JOBS=2
python -m pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r "$MTR_PREP/config/requirements-local.txt"
python -m pip install --no-build-isolation -e "$MTR_PREP/vendor/valeo4cast/scenarionet"
python -m pip install --no-build-isolation --no-deps -e "$MTR_PREP/vendor/valeo4cast/UniTraj"
python -m pip check
python -m pip freeze > "$MTR_PREP/config/requirements-resolved.txt"
python "$MTR_PREP/scripts/preflight.py"
