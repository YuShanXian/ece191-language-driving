const directions = {turn_left:'Turn left',turn_right:'Turn right',u_turn:'U-turn',go_straight:'Go straight'};
export function stopStatus(route) {
  if (route?.reverse) return {title:'Reverse complete',detail:'Choose the next instruction to continue.'};
  if (route?.boundaryReason) return {title:'Stopped at a map geometry boundary',detail:route.boundaryReason};
  const end=route?.stopContext;
  if (end?.kind==='junction') return {
    title:'Stopped at junction — choose a direction',
    detail:'No straight continuation from this lane. Mapped exits: '+end.available_actions.map(a=>directions[a]||a).join(' or ')+'.'
  };
  if (end?.kind==='map_end') return {title:'Stopped at the mapped road end',detail:'No connected exit is mapped here. Reverse or request a feasible U-turn.'};
  if (end?.kind==='requested_distance') return {title:'Requested distance reached',detail:'The requested maneuver includes a stop. Choose the next instruction to continue.'};
  return {title:'Planned route ended',detail:'Choose the next instruction to continue.'};
}
