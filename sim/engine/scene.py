"""One cached scene owns localization, topology, and pre-sampled lane geometry."""

from functools import lru_cache
import json, math, os
from pathlib import Path
import numpy as np
from shapely.geometry import LineString, Point
from shapely.affinity import affine_transform
from shapely.strtree import STRtree
from .geometry import ROOT, REPO_ROOT, arc, resample, tangent, angle_diff
from .map_data import load_graph
from .topology import RoadTopology


class Scene:
    def __init__(self, number):
        self.number = number
        scenes_root = REPO_ROOT / os.environ.get("ECE191_SCENES_ROOT", "sim/data/scenes")
        metadata = json.loads((scenes_root / f"scene{number:02d}.json").read_text(encoding="utf-8"))
        graph = load_graph(np.asarray(metadata["origin_xy_m"]), metadata["source_epsg"], metadata["map_path"])
        initial = metadata["start_pose"]["xy"]
        h = metadata["start_pose"]["heading"]
        c, s = math.cos(h), math.sin(h)
        transform = [c, s, -s, c, -c * initial[0] - s * initial[1], s * initial[0] - c * initial[1]]
        for node in graph.nodes.values():
            node.baseline = affine_transform(node.baseline, transform)
            node.polygon = affine_transform(node.polygon, transform)
        graph.surface = affine_transform(graph.surface, transform)
        self.graph = graph
        self.nodes = graph.nodes
        self.edges = graph.edges
        self.keys = list(self.nodes)
        self.lines = [self.nodes[k].baseline for k in self.keys]
        self.tree = STRtree(self.lines)
        self.points = {
            k: resample(np.asarray(n.baseline.coords)[:, :2]) for k, n in self.nodes.items()
        }
        self.arcs = {k: arc(p) for k, p in self.points.items()}
        self.topology = RoadTopology(graph)
        self.forward = self.topology.forward
        self.roads = [
            np.round(self.points[k][::2], 3).tolist() for k in self.keys if not k.startswith("J_")
        ]

    def locate(self, state):
        p = Point(state["xy"])
        h = state["heading"]
        preferred = state.get("node_id") or state.get("lane_key")
        if preferred in self.nodes:
            line = self.nodes[preferred].baseline
            if line.distance(p) < 0.8 and abs(angle_diff(tangent(line, state["xy"]), h)) < 0.5:
                return preferred, line.project(p)
        candidates = []
        for i in self.tree.query(p.buffer(2.2), predicate="intersects"):
            key = self.keys[int(i)]
            line = self.nodes[key].baseline
            error = line.distance(p)
            angle = abs(angle_diff(tangent(line, state["xy"]), h))
            if error < 2.2 and angle < math.radians(35):
                candidates.append((error + angle * 2, key, line.project(p)))
        if not candidates:
            return None
        _, key, s = min(candidates)
        return key, s

    def section(self, key, start=0, end=None):
        p = self.points[key]
        s = self.arcs[key]
        end = s[-1] if end is None else min(s[-1], end)
        start = min(max(0, start), end)
        distances = np.r_[start, s[(s > start + 1e-5) & (s < end - 1e-5)], end]
        return np.column_stack([np.interp(distances, s, p[:, i]) for i in range(2)])

    def continuation(self, key, start=0, limit=2800):
        return list(self.topology.corridor(key, start, limit))


@lru_cache(maxsize=7)
def get_scene(number):
    if number not in range(1, 8):
        raise ValueError("Scene must be 1–7")
    return Scene(number)
