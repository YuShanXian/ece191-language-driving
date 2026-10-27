"""Read-only MTR environment probe. Run with the intended inference Python."""
import importlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

repo = Path(__file__).resolve().parent.parent / "vendor/valeo4cast/UniTraj"
sys.path.insert(0, str(repo))
sys.path.insert(0, str(repo / "unitraj/models/mtr/ops"))

report = {"python": sys.version, "executable": sys.executable,
          "platform": platform.platform(), "nvcc": shutil.which("nvcc"), "modules": {}}
for name in ("torch", "pytorch_lightning", "hydra", "omegaconf", "numpy", "metadrive", "scenarionet", "unitraj", "lap"):
    try:
        module = importlib.import_module(name)
        report["modules"][name] = {"ok": True, "version": getattr(module, "__version__", None)}
    except Exception as exc:
        report["modules"][name] = {"ok": False, "error": str(exc)}
if report["modules"]["torch"]["ok"]:
    import torch
    report["cuda_available"] = torch.cuda.is_available()
    report["torch_cuda"] = torch.version.cuda
    if torch.cuda.is_available():
        report["gpu"] = torch.cuda.get_device_name(0)
        report["capability"] = torch.cuda.get_device_capability(0)
        try:
            (torch.ones(8, device="cuda") + 1).sum().item()
            report["cuda_tensor_test"] = "passed"
        except Exception as exc:
            report["cuda_tensor_test"] = str(exc)
# Use the same extension module names as the upstream wrappers. Loading a
# native module again under its fully qualified package name is unsafe.
for module in ("knn.knn_cuda", "attention.attention_cuda"):
    try:
        importlib.import_module(module)
        report["modules"][module] = {"ok": True}
    except Exception as exc:
        report["modules"][module] = {"ok": False, "error": str(exc)}
result = json.dumps(report, indent=2)
(Path(__file__).resolve().parent.parent / "runs/setup-reports/preflight-local.json").write_text(result, encoding="utf-8")
print(result)
sys.exit(0 if report.get("cuda_tensor_test") == "passed" and report["nvcc"] and all(x["ok"] for x in report["modules"].values()) else 1)
