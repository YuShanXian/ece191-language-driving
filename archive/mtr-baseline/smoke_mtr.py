"""Single-GPU, one-cache-chunk inference using the pinned Valeo4Cast source.

Requires a matching checkpoint and ScenarioNet dataset. Does not train.
Validated on the official Valeo4Cast validation scene recorded in sample-provenance.json.
"""
import argparse
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent / "vendor/valeo4cast")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True, help="Writable ScenarioNet subset; upstream creates a cache here")
    parser.add_argument("--output", type=Path, required=True, help="New output directory; existing path is refused")
    parser.add_argument("--ego-only", action="store_true", help="Adapter experiment only; use baseline data first")
    args = parser.parse_args()
    repo, ckpt, data, output = (p.resolve() for p in (args.repo, args.checkpoint, args.data, args.output))
    unitraj = repo / "UniTraj/unitraj"
    for path in (unitraj / "configs/challenge_config_noisy_val.yaml", ckpt, data / "dataset_summary.pkl"):
        if not path.exists():
            parser.error(f"Required input does not exist: {path}")
    if output.exists():
        parser.error(f"Use a new output directory: {output}")
    sys.path.insert(0, str(repo / "UniTraj"))
    sys.path.insert(0, str(unitraj))
    sys.path.insert(0, str(unitraj / "models/mtr/ops"))
    os.chdir(unitraj)
    import numpy as np
    import torch
    import pytorch_lightning as pl
    from hydra import compose, initialize_config_dir
    from omegaconf import OmegaConf
    from torch.utils.data import DataLoader
    from unitraj.models import build_model
    from unitraj.datasets import build_dataset

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required by this upstream MTR implementation")
    pl.seed_everything(42, workers=True)
    with initialize_config_dir(version_base=None, config_dir=str(unitraj / "configs")):
        cfg = compose(config_name="challenge_config_noisy_val")
    OmegaConf.set_struct(cfg, False)
    cfg.devices = [0]
    cfg.debug = False
    cfg.debug_challenge = True
    cfg.debug_scenario_id = ""
    cfg.smoke_current_time_index = 20
    cfg.debug_max_nb_scenarios = 1
    cfg.load_num_workers = 0
    cfg.overwrite_cache = False
    cfg.val_data_path = [data.as_posix()]
    cfg.ckpt_path = str(ckpt)
    cfg.only_train_on_ego = args.ego_only
    cfg.method.eval_batch_size = 8
    cfg = OmegaConf.merge(cfg, cfg.method)
    cfg["eval"] = True
    model = build_model(cfg)
    dataset = build_dataset(cfg, val=True)
    if not len(dataset):
        raise RuntimeError("No usable samples; inspect scenario schema, types and validity masks")
    loader = DataLoader(dataset, batch_size=1, num_workers=0, shuffle=False, collate_fn=dataset.collate_fn)
    trainer = pl.Trainer(accelerator="gpu", devices=[0], strategy="auto", logger=False,
                         enable_checkpointing=False, inference_mode=True, limit_predict_batches=1)
    # Explicit loading supports this trusted upstream Lightning checkpoint on
    # PyTorch >= 2.6, whose default weights_only behavior changed.
    payload = torch.load(ckpt, map_location="cpu", weights_only=False)
    model.load_state_dict(payload["state_dict"], strict=True)
    del payload
    import time
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    batches = trainer.predict(model, dataloaders=loader, return_predictions=True)
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    records = [record for batch in batches for record in batch[2]]
    if not records:
        raise RuntimeError("No predictions returned")
    for record in records:
        trajectories, scores = record["pred_trajs"], record["pred_scores"]
        if trajectories.shape != (5, 60, 2) or scores.shape != (5,):
            raise RuntimeError(f"Unexpected output shapes: {trajectories.shape}, {scores.shape}")
        if not np.isfinite(trajectories).all() or not np.isfinite(scores).all() or (scores < 0).any():
            raise RuntimeError("Invalid trajectories or scores")
    output.mkdir(parents=True)
    context = next(iter(loader))["input_dict"]
    manifest = []
    for index, record in enumerate(records):
        name = f"prediction_{index:04d}.npz"
        np.savez_compressed(output / name, trajectories=record["pred_trajs"], scores=record["pred_scores"],
                            reference_track=record["gt_trajs"],
                            map_polylines=context["map_polylines"][index].numpy(),
                            map_mask=context["map_polylines_mask"][index].numpy(),
                            history=context["obj_trajs_pos"][index].numpy(),
                            history_mask=context["obj_trajs_mask"][index].numpy(),
                            center=context["center_objects_world"][index].numpy(),
                            map_center=context["map_center"][index].numpy(),
                            target_index=context["track_index_to_predict"][index].numpy())
        manifest.append({"file": name, "scenario_id": str(record["scenario_id"]),
                         "object_id": str(record["object_id"]), "current_time_index": int(record["current_time_index"])})
    OmegaConf.save(cfg, output / "resolved_config.yaml")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output / "runtime.json").write_text(json.dumps({"checkpoint": str(ckpt), "data": str(data),
        "gpu": torch.cuda.get_device_name(0), "torch": torch.__version__, "prediction_seconds": elapsed,
        "peak_allocated_mib": torch.cuda.max_memory_allocated() / 2**20,
        "peak_reserved_mib": torch.cuda.max_memory_reserved() / 2**20,
        "predictions": len(records), "strict_weight_loading": True}, indent=2), encoding="utf-8")
    print(f"PASS: {len(records)} predictions saved to {output}")


if __name__ == "__main__":
    main()
