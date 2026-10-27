"""Verify downloaded checkpoint tensor compatibility; does not run inference."""
import argparse
import json
import os
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("checkpoint", type=Path)
args = parser.parse_args()
checkpoint = args.checkpoint.resolve()
root = Path(__file__).resolve().parent.parent
unitraj = root / "vendor/valeo4cast/UniTraj/unitraj"
sys.path[:0] = [str(unitraj.parent), str(unitraj), str(unitraj / "models/mtr/ops")]
os.chdir(unitraj)
import torch
from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf
from unitraj.models import build_model

with initialize_config_dir(version_base=None, config_dir=str(unitraj / "configs")):
    config = compose(config_name="challenge_config_noisy_val")
OmegaConf.set_struct(config, False)
config = OmegaConf.merge(config, config.method)
model = build_model(config)
# This is the explicit, user-approved upstream pretrained checkpoint.
payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
state = payload.get("state_dict", payload)
model.load_state_dict(state, strict=True)
model.cuda().eval()
result = {"checkpoint": str(checkpoint), "strict_state_dict": "passed",
          "parameters": sum(p.numel() for p in model.parameters()),
          "gpu": torch.cuda.get_device_name(0),
          "gpu_allocated_mb": torch.cuda.memory_allocated() / 2**20,
          "note": "Loaded on GPU; real-data inference has not been tested."}
(root / "runs/setup-reports/checkpoint-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
