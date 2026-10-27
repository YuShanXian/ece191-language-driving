// Keep direction and the origin of a path visible beside the moving vehicle.
export function motionStatus(vehicle) {
  const route = vehicle.route;
  if (!route) return 'Ready';
  const direction = route.reverse ? 'Reverse' : 'Forward';
  const sources = {
    traveled_path: 'Retracing traveled path',
    mapped_reverse: 'Reversing on mapped lane',
    current_lane_reverse: 'Reversing along the current lane and its bends',
    inferred_connector: 'Maneuver uses a completed connection',
    mapped_connector: 'Maneuver uses mapped connection',
    live_junction_replan: 'Junction exit replanned from current pose',
    lane_change: 'Lane-change path',
    prepared_mapped_turn: 'One preparatory lane change, then mapped turn',
    recovery_turn: 'Turnaround in mapped road space',
    recovery_three_point: 'Three-point turn, stop between gears',
    mapped_corridor: 'Connected lane corridor'
  };
  const reasons = {target:'target', reverse:'reverse cap',
    route:'route cap', curve:'curve', end:'route end'};
  const motion = vehicle.paused ? 'Paused' : vehicle.ended ? 'Complete' :
    `${(vehicle.speed * 3.6).toFixed(1)} km/h · ${reasons[vehicle.speedReason]} ${(vehicle.effectiveTarget * 3.6).toFixed(1)} km/h`;
  return `${direction} · ${motion}\n${sources[route.geometrySource] || 'Planned path'}`;
}
