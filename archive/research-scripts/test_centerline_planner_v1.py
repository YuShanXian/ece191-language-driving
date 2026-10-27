import numpy as np,json,builtins
from pathlib import Path
from unittest.mock import patch
from shapely.geometry import LineString
from trajectory_checks import RoadGraph,RoadNode,motion_check
from centerline_trajectory_planner import CONFIG,geometry,time_parameterize
from mtr_project.paths import ROOT,write_json
center=np.array([0.,0.,0.,4.8,2.,0.,0.,5.,0.,0.]);a=np.linspace(0,np.pi/2,80);turn=np.c_[20*np.sin(a),20*(1-np.cos(a))];turn=np.vstack([turn,[[20,100]]]);cases=[('straight',[[0,0],[100,0]]),('lane_change',[[0,3.5],[100,3.5]]),('left_turn',turn)];tests=[]
for name,pts in cases:
 line=LineString(pts);g=RoadGraph([RoadNode('Ltest',line.buffer(6),line,'lane',1,1)],{})
 for horizon in [6.,12.,30.]:
  with patch.object(builtins,'open',side_effect=AssertionError('planner read a file')),patch.object(Path,'open',side_effect=AssertionError('planner read a file')):
   shape=geometry(g,['Ltest'],center,18);p,t=time_parameterize(shape,center,[0.,0.],{**CONFIG,'horizon_s':horizon})
  assert p.shape==(round(horizon*10)+1,2) and np.isfinite(p).all();assert np.allclose(p[0],center[:2]);assert min(np.diff(t['progress_m']))>=-1e-8;assert max(t['progress_m'])<shape['length']-.1;assert max(t['speed_mps'])<=CONFIG['cruise_speed_mps']+.1
  motion=motion_check(p,center[7:9],initial_acceleration=[0.,0.]);assert motion['passed'],(name,horizon,motion)
  tests.append({'case':name,'horizon_s':horizon,'motion':motion,'no_file_access':True})
write_json(ROOT/'runs/project-v3/centerline-planner-v1/synthetic-verification.json',{'passed':True,'tests':tests});print('9 synthetic tests passed: straight, lane change, turn; 6/12/30 seconds; no file access, finite points, monotone progress, speed and motion checks.')
