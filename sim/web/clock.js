// Rendering can be throttled to one frame per second in an occluded window.
// One shared monotonic clock drives both callbacks; physics still uses small steps.
export class DriveClock {
  constructor(now) { this.last = now; }
  advance(now, vehicle, pipeline, ready) {
    if (now <= this.last) return {dt: 0, moved: 0};
    const elapsed = Math.max(0, (now - this.last) / 1000);
    this.last = now;
    // A suspended computer must not teleport through minutes of unseen driving.
    const dt = Math.min(2, elapsed);
    let remaining = dt, moved = 0;
    while (remaining > 1e-8) {
      const step = Math.min(.05, remaining);
      moved += vehicle.tick(step);
      if (ready) pipeline.tick(step);
      remaining -= step;
    }
    return {dt, moved};
  }
}
