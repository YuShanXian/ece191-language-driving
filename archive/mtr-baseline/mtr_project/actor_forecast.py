"""Small causal motion baselines. These do not model driver intent or interaction."""
import numpy as np

METHODS=('database_velocity','history_linear','history_turn_rate')

def fit_observed_motion(times,positions,headings,current_velocity):
    times=np.asarray(times,float);positions=np.asarray(positions,float);headings=np.asarray(headings,float)
    velocity=np.asarray(current_velocity,float)
    if times.ndim!=1 or positions.shape!=(len(times),2) or headings.shape!=(len(times),):raise ValueError('Invalid history shape')
    if not len(times) or not all(np.isfinite(a).all() for a in [times,positions,headings,velocity]):raise ValueError('Invalid observed history')
    if velocity.shape!=(2,) or np.any(np.diff(times)<=0):raise ValueError('Invalid time or velocity')
    # times are relative to the present observation. Positive values are forbidden.
    if times[-1]!=0 or np.any(times>0):raise ValueError('History must end at time zero; future observations forbidden')
    result={'xy':positions[-1].tolist(),'heading':float(headings[-1]),'database_velocity':velocity.tolist(),
            'history_velocity':velocity.tolist(),'yaw_rate':0.,'history_available':False,'fallback':'insufficient_history'}
    if len(times)<4 or times[-1]-times[0]<.4 or np.max(np.diff(times))>.3:return result
    design=np.c_[times,np.ones(len(times))]
    coefficients=np.linalg.lstsq(design,positions,rcond=None)[0]
    heading_coefficients=np.linalg.lstsq(design,np.unwrap(headings),rcond=None)[0]
    # A fixed plausibility gate; invalid turn fitting falls back to linear motion.
    rate=float(heading_coefficients[0]);speed=np.linalg.norm(coefficients[0])
    if speed>40:return result
    result.update(history_velocity=coefficients[0].tolist(),history_available=True,fallback=None,
                  position_fit_rmse_m=float(np.sqrt(np.mean((design@coefficients-positions)**2))),
                  yaw_rate=rate if abs(rate)<=1 and speed>=.5 else 0.)
    return result


def forecast(model,times,method):
    if method not in METHODS:raise ValueError('Unknown forecast method')
    times=np.asarray(times,float)
    if times.ndim!=1 or np.any(times<0) or not np.isfinite(times).all():raise ValueError('Invalid future times')
    velocity=np.asarray(model['database_velocity' if method=='database_velocity' else 'history_velocity'])
    omega=model['yaw_rate'] if method=='history_turn_rate' else 0.
    if abs(omega)<1e-6:offset=times[:,None]*velocity
    else:
        sine=np.sin(omega*times)/omega;cosine=(1-np.cos(omega*times))/omega
        offset=np.c_[velocity[0]*sine-velocity[1]*cosine,velocity[0]*cosine+velocity[1]*sine]
    return np.asarray(model['xy'])+offset,model['heading']+omega*times
