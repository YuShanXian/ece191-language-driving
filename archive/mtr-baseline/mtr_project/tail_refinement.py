"""A smooth, explicitly bounded lateral adjustment to a proposed trajectory.

This produces a new map-guided curve, not a raw MTR prediction. The caller must
recheck every geometric/dynamic constraint and deviation from raw predictions.
"""
import math
import numpy as np


def tail_lateral_shift(points,normal,amount,start_seconds=3.,dt=.1):
    points=np.asarray(points,float);normal=np.asarray(normal,float)
    if points.ndim!=2 or points.shape[1]!=2 or len(points)<4 or not np.isfinite(points).all():
        raise ValueError('Finite planar trajectory required')
    if normal.shape!=(2,) or not np.isfinite(normal).all() or abs(np.linalg.norm(normal)-1)>1e-6:
        raise ValueError('Unit lateral direction required')
    if not all(math.isfinite(x) for x in [amount,start_seconds,dt]) or dt<=0 or abs(amount)>1.:
        raise ValueError('Finite parameters and at most 1 m shift required')
    horizon=(len(points)-1)*dt
    if not 0<=start_seconds<horizon:raise ValueError('Tail start must precede horizon')
    phase=np.clip((np.arange(len(points))*dt-start_seconds)/(horizon-start_seconds),0,1)
    blend=10*phase**3-15*phase**4+6*phase**5
    return points+blend[:,None]*amount*normal
