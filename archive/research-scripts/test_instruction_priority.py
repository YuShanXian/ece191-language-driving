"""Behavior tests: action selection must not silently depend on safety veto."""
import numpy as np
from instruction_priority_selector import select_priority
center=np.zeros(7)
x=np.linspace(0,30,60);straight=np.c_[x,np.zeros(60)]
left=np.c_[20*np.sin(np.linspace(0,np.pi/2,60)),20*(1-np.cos(np.linspace(0,np.pi/2,60)))]
rows=[{'candidate':1,'score':.8,'route':{'matched':True,'lane_changes':[]},'rejected_by':['constant_velocity_collision'],'passes_current_checks':False}]
a=select_priority(rows,[left],center,'turn_left')
assert a['candidate']==1 and a['risk_flags']==['constant_velocity_collision']
assert select_priority(rows,[straight],center,'turn_left')['candidate'] is None
shift=np.c_[x,3.5*(3*(x/30)**2-2*(x/30)**3)]
b=select_priority(rows,[shift],center,'lane_change_left')
assert b['candidate']==1 and b['evidence']=='lateral_motion_only'
assert select_priority(rows,[shift],center,'lane_change_right')['candidate'] is None
print('4 behavior checks passed')
