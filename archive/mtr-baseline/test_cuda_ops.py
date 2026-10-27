"""Numerical smoke tests for the actual CUDA kernels; no trained-model claims."""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "vendor/valeo4cast/UniTraj/unitraj/models/mtr/ops"))
import torch
from knn import knn_utils
from attention import attention_utils_v2 as attention

torch.manual_seed(42)
xyz = torch.randn(8, 3, device="cuda").contiguous()
query = torch.randn(12, 3, device="cuda").contiguous()
batch = torch.zeros(8, dtype=torch.int32, device="cuda")
offsets = torch.tensor([0, 12], dtype=torch.int32, device="cuda")
reference = torch.cdist(xyz, query).topk(3, largest=False).indices.sort(dim=1).values
for fn in (knn_utils.knn_batch, knn_utils.knn_batch_mlogk):
    actual = fn(xyz, query, batch, offsets, 3).long().sort(dim=1).values
    torch.testing.assert_close(actual, reference)

q = torch.randn(4, 2, 8, device="cuda")
k = torch.randn(6, 2, 8, device="cuda")
pair = torch.tensor([[0, 2, 4], [1, 3, 5], [0, 1, 2], [3, 4, 5]], dtype=torch.int32, device="cuda")
q_count = torch.tensor([4], dtype=torch.int32, device="cuda")
k_count = torch.tensor([6], dtype=torch.int32, device="cuda")
pair_batch = torch.zeros(4, dtype=torch.int32, device="cuda")
actual = attention.attention_weight_computation(q_count, k_count, pair_batch, pair, q, k)
expected = (q[:, None, :, :] * k[pair.long()]).sum(-1)
torch.testing.assert_close(actual, expected, rtol=1e-4, atol=1e-5)
torch.cuda.synchronize()
result = {"gpu": torch.cuda.get_device_name(0), "torch": torch.__version__,
          "knn_batch": "passed", "knn_batch_mlogk": "passed", "attention_weight_v2": "passed",
          "note": "Synthetic numerical kernel checks only. Pretrained inference remains a separate milestone."}
text = json.dumps(result, indent=2)
(root / "runs/setup-reports/cuda-ops-result.json").write_text(text, encoding="utf-8")
print(text)
