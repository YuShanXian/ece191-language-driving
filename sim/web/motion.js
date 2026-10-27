export const angleDiff = (a, b) => Math.atan2(Math.sin(a - b), Math.cos(a - b));
export class Route {
  constructor(data) {
    if (!Array.isArray(data.points) || data.points.length < 2) throw Error('Empty route');
    this.points = data.points;
    this.segments = data.segments || [];
    this.movements = data.movements || [];
    this.reverse = !!data.reverse;
    this.retraceHistory = data.retrace_history !== false;
    this.stopContext = data.stop_context;
    this.boundaryReason = data.boundary_reason;
    this.geometrySource = data.geometry_source || (data.lane_change ? 'lane_change' : 'mapped_corridor');
    this.stop = data.stop_at_end !== false;
    this.arc = [0];
    for (let i = 1; i < this.points.length; i++) {
      const a = this.points[i - 1],
        b = this.points[i];
      if (![...a, ...b].every(Number.isFinite)) throw Error('Invalid route');
      this.arc.push(this.arc.at(-1) + Math.hypot(b[0] - a[0], b[1] - a[1]));
    }
    this.length = this.arc.at(-1);
  }
  pointAt(distance) {
    distance = Math.max(0, Math.min(distance, this.length));
    let lo = 0,
      hi = this.arc.length - 1;
    while (hi - lo > 1) {
      const m = (lo + hi) >> 1;
      if (this.arc[m] <= distance) lo = m;
      else hi = m;
    }
    const a = this.points[lo],
      b = this.points[hi],
      u = (distance - this.arc[lo]) / Math.max(1e-8, this.arc[hi] - this.arc[lo]);
    return [a[0] + u * (b[0] - a[0]), a[1] + u * (b[1] - a[1])];
  }
  at(distance) {
    distance = Math.max(0, Math.min(distance, this.length));
    // A metric tangent remains stable at the rounded millimeter-length tail.
    const a = this.pointAt(distance - .25), b = this.pointAt(distance + .25);
    return {
      xy: this.pointAt(distance),
      heading: Math.atan2(b[1] - a[1], b[0] - a[0]) + (this.reverse ? Math.PI : 0),
      node_id: this.segments.find(s => distance >= s.start - .01 && distance < s.end - .01)?.node_id || this.segments.at(-1)?.node_id
    };
  }
  project(point, limit = Infinity) {
    let best = {
      distance: Infinity,
      s: 0
    };
    for (let i = 1; i < this.points.length && this.arc[i - 1] <= limit; i++) {
      const a = this.points[i - 1],
        b = this.points[i],
        dx = b[0] - a[0],
        dy = b[1] - a[1],
        length = Math.hypot(dx, dy);
      const u = Math.max(0, Math.min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / Math.max(1e-12, length * length)));
      const d = Math.hypot(point[0] - a[0] - u * dx, point[1] - a[1] - u * dy);
      if (d < best.distance) best = {
        distance: d,
        s: this.arc[i - 1] + u * length
      };
    }
    return best;
  }
  speedLimit(s) {
    let limit = 15;
    // Preview curvature so the vehicle brakes before entering a tight turn.
    for (let d = 0; d < 18; d += 2) {
      const a = this.at(s + d),
        b = this.at(s + d + 2),
        curvature = Math.abs(angleDiff(b.heading, a.heading)) / 2;
      const corner = Math.sqrt(2.2 / Math.max(.001, curvature));
      limit = Math.min(limit, Math.sqrt(corner * corner + 3 * d));
    }
    return limit;
  }
}

export class Vehicle {
  constructor() {
    this.reset();
  }
  reset(pose = {
    xy: [0, 0],
    heading: 0,
    speed: 0
  }) {
    this.pose = {
      ...pose,
      xy: [...pose.xy]
    };
    this.route = null;
    this.distance = 0;
    this.target = 20 / 3.6;
    this.speed = pose.speed || 0;
    this.paused = false;
    this.epoch = 0;
    this.history = [pose.xy];
    this.movingSeconds = 0;
    this.totalDistance = 0;
    this.jumps = 0;
    this.maxHeadingStep = 0;
    this.ended = false;
    this.speedCap = 15;
    this.speedReason = 'target';
    this.effectiveTarget = this.target;
  }
  state() {
    return {
      ...this.pose,
      speed: this.speed,
      target_speed_mps: this.target,
      history: this.history.slice(-1200)
    };
  }
  install(data, {
    maxAdvance = 20,
    speedCap = 15
  } = {}) {
    const route = new Route(data),
      projection = route.project(this.pose.xy, maxAdvance);
    if (route.length - projection.s < .02) return false;
    if (projection.distance > .12) return false;
    const location = route.at(projection.s);
    if (Math.abs(angleDiff(location.heading, this.pose.heading)) > .35) return false;
    this.route = route;
    this.distance = projection.s;
    this.ended = false;
    this.speedCap = speedCap;
    this.epoch++;
    // Keep the exact live position until the next physical integration step.
    return true;
  }
  stop(immediate = false) {
    this.target = 0;
    if (immediate) this.speed = 0;
  }
  tick(dt) {
    if (this.paused || !this.route || this.ended) return 0;
    dt = Math.max(0, Math.min(.1, dt));
    const remaining = Math.max(0, this.route.length - this.distance);
    if (remaining < .015) {
      this.speed = 0;
      this.ended = true;
      return 0;
    }
    const limits = [['target', this.target], [this.route.reverse ? 'reverse' : 'route', this.speedCap],
      ['curve', this.route.speedLimit(this.distance)], ['end', Math.sqrt(3 * remaining)]];
    const [reason, target] = limits.reduce((best, item) => item[1] < best[1] ? item : best);
    this.speedReason = reason;
    this.effectiveTarget = target;
    this.speed = Math.max(0, this.speed + Math.max(-2.5 * dt, Math.min(1.5 * dt, target - this.speed)));
    const movement = Math.min(remaining, this.speed * dt);
    this.distance += movement;
    const next = this.route.at(this.distance),
      jump = Math.hypot(next.xy[0] - this.pose.xy[0], next.xy[1] - this.pose.xy[1]);
    if (jump > movement + .35) this.jumps++;
    this.maxHeadingStep = Math.max(this.maxHeadingStep, Math.abs(angleDiff(next.heading, this.pose.heading)));
    this.pose = next;
    this.totalDistance += movement;
    if (movement > .0001) this.movingSeconds += dt;
    if (this.route.reverse && !this.route.retraceHistory) {
      // A newly steered reverse path is not a forward trail that can be
      // reversed again. Start a fresh forward-history segment at this pose.
      this.history = [[...next.xy]];
    } else if (this.route.reverse) {
      let best = Infinity,
        index = this.history.length - 1;
      for (let i = this.history.length - 1; i >= 0; i--) {
        const d = Math.hypot(this.history[i][0] - next.xy[0], this.history[i][1] - next.xy[1]);
        if (d < best) {
          best = d;
          index = i;
        }
      }
      const ahead = (this.history[index][0]-next.xy[0])*Math.cos(next.heading) +
                    (this.history[index][1]-next.xy[1])*Math.sin(next.heading);
      if (ahead > .001 && index > 0) index--;
      this.history = this.history.slice(0, index + 1);
    }
    if (Math.hypot(next.xy[0] - this.history.at(-1)[0], next.xy[1] - this.history.at(-1)[1]) > .35) this.history.push([...next.xy]);
    if (this.history.length > 5000) this.history.splice(0, 1000);
    return movement;
  }
}
