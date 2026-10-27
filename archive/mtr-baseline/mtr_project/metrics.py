"""Evaluation-only trajectory errors. Recorded future never enters selection."""
import numpy as np

def trajectory_error(prediction, target, valid=None):
    p=np.asarray(prediction,dtype=float);t=np.asarray(target,dtype=float)
    if p.shape!=t.shape or p.ndim!=2 or p.shape[1]!=2:raise ValueError('Expected equal [time,2] shapes')
    if not np.isfinite(p).all():raise ValueError('Prediction has nonfinite coordinates')
    mask=np.ones(len(p),dtype=bool) if valid is None else np.asarray(valid,dtype=bool)
    if mask.shape!=(len(p),):raise ValueError('Invalid validity mask')
    if not mask.any():return {'ade_m':None,'fde_m':None,'valid_points':0,'horizon_complete':False}
    if not np.isfinite(t[mask]).all():raise ValueError('Valid target is nonfinite')
    distance=np.linalg.norm(p[mask]-t[mask],axis=1)
    # Only report FDE at the requested final horizon, not the last available point.
    return {'ade_m':float(distance.mean()),'fde_m':float(np.linalg.norm(p[-1]-t[-1])) if mask[-1] else None,
            'valid_points':int(mask.sum()),'horizon_complete':bool(mask.all())}

def summarize_optional(values):
    finite=[x for x in values if x is not None and np.isfinite(x)]
    return {'count':len(finite),'mean':float(np.mean(finite)) if finite else None,
            'median':float(np.median(finite)) if finite else None}
