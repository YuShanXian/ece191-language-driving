"""Explicit bounded smoothing of MTR positions, not a modification to raw predictions.

Quadratic least squares: position fidelity + acceleration + jerk; exact initial
position and first-interval velocity. Every refined path must be rechecked.
"""
import numpy as np

def refine(points,initial_velocity,dt=.1,initial_acceleration=None):
    points=np.asarray(points,float);n=len(points)
    eye=np.eye(n)
    d2=np.diff(eye,n=2,axis=0)/dt**2
    d3=np.diff(eye,n=3,axis=0)/dt**3
    # Position deviations in metres dominate; derivative terms suppress jitter.
    A=np.vstack([eye,.05*d2,.02*d3])
    b=np.vstack([points,np.zeros((len(d2)+len(d3),2))])
    fixed=np.vstack([points[0],points[0]+np.asarray(initial_velocity)*dt])
    if initial_acceleration is not None:
        # v0 is the measured previous-interval velocity, not an instantaneous fit.
        # With constant acceleration, subsequent interval velocities are v0+a*dt,
        # then v0+2*a*dt. Fix both intervals to avoid inventing zero acceleration.
        v=np.asarray(initial_velocity);a=np.asarray(initial_acceleration)
        fixed=np.vstack([points[0],points[0]+v*dt+a*dt**2,points[0]+2*v*dt+3*a*dt**2])
    k=len(fixed)
    solution=np.linalg.lstsq(A[:,k:],b-A[:,:k]@fixed,rcond=None)[0]
    result=np.vstack([fixed,solution])
    deviation=np.linalg.norm(result-points,axis=1)
    return result,{'method':'constrained quadratic smoothing v2 with past acceleration' if initial_acceleration is not None else 'constrained quadratic smoothing v1','dt':dt,
                   'initial_acceleration_mps2':None if initial_acceleration is None else np.asarray(initial_acceleration).tolist(),
                   'acceleration_weight':.05,'jerk_weight':.02,
                   'max_deviation_m':float(deviation.max()),'max_allowed_deviation_m':1.,
                   'within_deviation_bound':bool(deviation.max()<=1.),
                   'scope':'Derived curve, not raw MTR. Requires all downstream checks again.'}
