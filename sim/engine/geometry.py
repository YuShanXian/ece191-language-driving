"""Shared metric geometry; every route uses distance, never frame-index time."""

from dataclasses import dataclass
from pathlib import Path
import math, os
import numpy as np
from shapely.geometry import Point, Polygon, LineString, box
from shapely.ops import unary_union
from shapely.prepared import prep

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT = (REPO_ROOT / os.environ.get("ECE191_DATA_ROOT", ".")).resolve()


@dataclass
class RoadNode:
    key: str
    polygon: object
    baseline: object
    kind: str
    lane_group: int | None = None
    lane_index: int | None = None


class RoadGraph:
    def __init__(self, nodes, edges):
        self.nodes = {n.key: n for n in nodes}
        self.edges = edges
        self.lane_groups = {}
        for node in self.nodes.values():
            if node.kind == "lane":
                self.lane_groups.setdefault(node.lane_group, []).append(node)
        self.surface = unary_union([n.polygon for n in nodes]).buffer(0.05)


def angle_diff(a, b):
    return float(np.arctan2(np.sin(a - b), np.cos(a - b)))


def tangent(line, point):
    s = line.project(Point(point))
    a = np.asarray(line.interpolate(max(0, s - 0.5)).coords[0])[:2]
    b = np.asarray(line.interpolate(min(line.length, s + 0.5)).coords[0])[:2]
    return math.atan2(b[1] - a[1], b[0] - a[0])


def footprint(xy, heading, length, width, margin=0):
    corners = np.array([[1, 1], [1, -1], [-1, -1], [-1, 1]], float) * [
        length / 2 + margin,
        width / 2 + margin,
    ]
    c, s = np.cos(heading), np.sin(heading)
    return Polygon(corners @ np.array([[c, s], [-s, c]]) + xy)


def clean(points):
    p = np.asarray(points, dtype=float)
    return p[np.r_[True, np.linalg.norm(np.diff(p, axis=0), axis=1) > 1e-5]]


def arc(points):
    return np.r_[0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]


def resample(points, step=0.5):
    p = clean(points)
    s = arc(p)
    if len(p) < 2:
        return p
    # Avoid an almost-zero final segment when accumulated arc length is 10 + epsilon.
    # Its numerically unstable heading otherwise looks like a right-angle corner.
    target = np.arange(0, s[-1] - 1e-5, step)
    target = np.r_[target, s[-1]]
    return np.column_stack([np.interp(target, s, p[:, i]) for i in range(2)])


def heading(points, at_end=False):
    p = np.asarray(points)
    d = p[-1] - p[max(0, len(p) - 4)] if at_end else p[min(len(p) - 1, 3)] - p[0]
    return float(math.atan2(d[1], d[0]))


def validate_path(points):
    raw = clean(points)
    if len(raw) > 2:
        steps = np.diff(raw, axis=0)
        lengths = np.linalg.norm(steps, axis=1)
        cosine = np.sum(steps[:-1]*steps[1:],axis=1) / np.maximum(1e-12,lengths[:-1]*lengths[1:])
        if np.any((cosine < -.5) & (np.minimum(lengths[:-1],lengths[1:]) > .005)):
            return False, 'Route reverses direction between adjacent samples'
    p = resample(points, 0.5)
    if len(p) < 2 or not np.isfinite(p).all():
        return False, "Invalid route coordinates"
    d = np.diff(p, axis=0)
    length = np.linalg.norm(d, axis=1)
    h = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
    # A right-angle corner must never become a playable trajectory.
    curvature = np.abs(np.diff(h)) / np.maximum(0.25, (length[:-1] + length[1:]) / 2)
    if len(curvature) and np.max(curvature) > 0.32:
        return False, "Route has an abrupt steering discontinuity"
    return True, ""


def reverse_clearance(route, surface):
    """A vehicle already over a map endpoint may retreat, never worsen it.

    Check the whole body every 0.25 m. Once back inside, no part may leave
    mapped drivable space again. This also rejects fabricated history paths.
    """
    p=np.asarray(route['points']);s=arc(p)
    d=np.linspace(0,s[-1],max(2,int(s[-1]/.25)+1))
    xy=np.column_stack([np.interp(d,s,p[:,i]) for i in (0,1)])
    tangent=np.gradient(xy,axis=0)
    hs=np.arctan2(tangent[:,1],tangent[:,0])+math.pi
    bounds=LineString(xy).bounds
    surface=surface.intersection(box(bounds[0]-4,bounds[1]-4,bounds[2]+4,bounds[3]+4))
    prepared=prep(surface)
    if not surface.buffer(.02).covers(LineString(xy)):
        return False
    bodies=[footprint(x,h,4.8,2) for x,h in zip(xy,hs)]
    outside=[0 if prepared.covers(body) else body.difference(surface).area for body in bodies]
    # Permit only the pre-existing endpoint overhang while it shrinks.
    return outside[-1]<.02 and all(b<=a+.02 for a,b in zip(outside,outside[1:]))


