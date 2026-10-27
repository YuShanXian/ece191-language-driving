"""Plot real-scene MTR predictions in each target's local frame."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("output", type=Path)
args = p.parse_args()
manifest = json.loads((args.output / "manifest.json").read_text())
fig, axes = plt.subplots(2, 4, figsize=(18, 9), constrained_layout=True)
colors = ["#e76f51", "#2a9d8f", "#457b9d", "#b565a7", "#e9a520"]
for ax, record in zip(axes.flat, manifest):
    d = np.load(args.output / record["file"])
    center = d["center"]
    angle = center[6]
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    local = (d["trajectories"] - center[:2] - d["map_center"][:2]) @ rotation
    for line, mask in zip(d["map_polylines"], d["map_mask"]):
        points = line[mask.astype(bool), :2]
        if len(points):
            ax.plot(points[:, 0], points[:, 1], color="#c8cdd2", lw=0.6, zorder=0)
    idx = int(d["target_index"])
    history = d["history"][idx][d["history_mask"][idx].astype(bool), :2]
    ax.plot(history[:, 0], history[:, 1], "k.-", lw=2, ms=3, label="Observed history")
    ax.scatter([0], [0], c="black", s=25, zorder=5)
    for mode, (trajectory, score) in enumerate(zip(local, d["scores"])):
        ax.plot(trajectory[:, 0], trajectory[:, 1], color=colors[mode], lw=1.7,
                label=f"Mode {mode+1}: {score:.3f}")
    bound = np.concatenate([local.reshape(-1, 2), history], axis=0)
    lo, hi = bound.min(axis=0)-8, bound.max(axis=0)+8
    ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1])
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(f"Object {str(record['object_id'])[:12]} | frame {record['current_time_index']}", fontsize=10)
    ax.set_xlabel("Forward x (m)"); ax.set_ylabel("Left y (m)")
    ax.grid(alpha=0.15); ax.legend(fontsize=7, loc="best")
for ax in list(axes.flat)[len(manifest):]:
    ax.axis("off")
fig.suptitle("Pretrained MTR on a real Valeo4Cast validation scene\n5 candidate trajectories per target; smoke test, not a prediction-quality benchmark", fontsize=15)
fig.savefig(args.output / "trajectories.png", dpi=160)
plt.close(fig)
print(args.output / "trajectories.png")
