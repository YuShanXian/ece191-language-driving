"""Synthetic interface probe only: find the installed iLQR terminal-reference boundary."""
import inspect
import json
import numpy as np
import yaml
from nuplan.common.actor_state.state_representation import TimePoint
from nuplan.planning.simulation.simulation_time_controller.simulation_iteration import SimulationIteration
from nuplan.planning.simulation.controller.tracker.ilqr_tracker import ILQRTracker
from nuplan.planning.simulation.controller.tracker.ilqr.ilqr_solver import ILQRSolver, ILQRSolverParameters, ILQRWarmStartParameters
from nuplan.planning.simulation.controller.tracker import tracker_utils
from mtr_project.tracking_diagnostic import make_reference
from mtr_project.paths import ROOT, sha256, write_json


def typed_config(mapping):
    result = {}
    for key, value in mapping.items():
        if key.startswith('_'): continue
        result[key] = [float(x) for x in value] if isinstance(value,list) else int(value) if key=='max_ilqr_iterations' else float(value)
    return result


def main():
    path=ROOT/'config/controller-reference-v1/ilqr_tracker.yaml'
    config=yaml.safe_load(path.read_text())
    params=typed_config(config['ilqr_solver']['solver_params'])
    params['max_solve_time']=None
    warm=typed_config(config['ilqr_solver']['warm_start_params'])
    t=np.arange(121)*.05
    trajectory,_=make_reference(np.column_stack([5*t,0*t]),0.,.05)
    checks=[]
    for time in [0.,5.4,5.6,5.8,5.9]:
        tracker=ILQRTracker(config['n_horizon'],ILQRSolver(ILQRSolverParameters(**params),ILQRWarmStartParameters(**warm)))
        current=SimulationIteration(TimePoint(round(time*1e6)),round(time/.2))
        following=SimulationIteration(TimePoint(round((time+.2)*1e6)),round(time/.2)+1)
        reference=tracker._get_reference_trajectory(current,trajectory)
        record={'current_time_s':time,'reference_states':len(reference),'last_reference_time_within_6s':True}
        try:
            command=tracker.track_trajectory(current,following,trajectory.get_state_at_time(current.time_point),trajectory)
            record.update(status='command_returned',acceleration=float(command.rear_axle_acceleration_2d.x),tire_rate=float(command.tire_steering_rate))
        except (AssertionError,IndexError,ValueError) as error:
            record.update(status='failed_short_reference',exception_type=type(error).__name__,message=str(error))
        checks.append(record)
    result={'scope':'Synthetic constant-speed straight path, no scene/model quality result. Only timeout disabled to avoid hardware-dependent termination during interface probing.',
        'source_sha256':{str(path.relative_to(ROOT)):sha256(path),'scripts/mtr_project/tracking_diagnostic.py':sha256(ROOT/'scripts/mtr_project/tracking_diagnostic.py')},
        'sdk_source_sha256':{inspect.getfile(item):sha256(inspect.getfile(item)) for item in [ILQRTracker,ILQRSolver,tracker_utils]},
        'generator_sha256':sha256(__file__),'checks':checks}
    output=ROOT/'runs/project-v2/catalog/ilqr-boundary-probe.json'
    if output.exists(): raise FileExistsError('Preserve the recorded interface probe')
    write_json(output,result)
    print(json.dumps(checks,indent=2))


if __name__=='__main__':main()
