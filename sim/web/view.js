import {motionStatus} from './motion-status.js';
import {stopStatus} from './stop-status.js';
const labels = {
  parsing: 'Parsing language',
  braking_reverse: 'Stopping before reverse',
  braking_maneuver: 'Stopping to maneuver',
  queued: 'Queued',
  planning: 'Checking route',
  waiting: 'Waiting',
  approaching: 'Approaching',
  executing: 'Executing',
  completed: 'Completed',
  applied: 'Applied',
  blocked: 'Route ended',
  timed_out: 'Not executed: timeout',
  error: 'Request failed',
  unsupported: 'Needs clarification',
  cancelled: 'Cancelled',
  skipped: 'Skipped',
  stopping: 'Stopping'
};
export class View {
  constructor(vehicle, pipeline) {
    this.vehicle = vehicle;
    this.pipeline = pipeline;
    this.roads = [];
    this.bounds = [];
    this.canvas = document.querySelector('#map');
    this.ctx = this.canvas.getContext('2d');
    this.lastUI = 0;
    this.layoutShifts = 0;
    this.stall = 0;
    this.longestStall = 0;
    this.queueFocusSignature = null;
    document.querySelector('#followQueue').addEventListener('change',()=>{this.queueFocusSignature=null;});
    try {
      new PerformanceObserver(list => {
        for (const e of list.getEntries())
          if (!e.hadRecentInput) this.layoutShifts += e.value > .01 ? 1 : 0;
      }).observe({
        type: 'layout-shift',
        buffered: true
      });
    } catch {}
  }
  setRoads(roads) {
    this.roads = roads;
    this.bounds = roads.map(p => p.reduce((b, q) => [Math.min(b[0], q[0]), Math.max(b[1], q[0]), Math.min(b[2], q[1]), Math.max(b[3], q[1])], [Infinity, -Infinity, Infinity, -Infinity]));
  }
  render(now, dt, moved) {
    const v = this.vehicle,
      canvas = this.canvas,
      ctx = this.ctx,
      w = canvas.clientWidth,
      h = canvas.clientHeight,
      dpr = devicePixelRatio;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const scale = Math.min(w / 120, h / 95),
      car = v.pose.xy;
    const drawLine = (points, color, width) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.beginPath();
      points.forEach((p, i) => {
        const x = w / 2 + (p[0] - car[0]) * scale,
          y = h / 2 - (p[1] - car[1]) * scale;
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      });
      ctx.stroke();
    };
    for (let i = 0; i < this.roads.length; i++) {
      const b = this.bounds[i];
      if (b[1] > car[0] - 80 && b[0] < car[0] + 80 && b[3] > car[1] - 65 && b[2] < car[1] + 65) drawLine(this.roads[i], '#ccd7e0', 1);
    }
    if (v.route) {
      const p = v.route.points.filter((point, i) => v.route.arc[i] >= v.distance - 8 && v.route.arc[i] <= v.distance + 180);
      drawLine(p, v.route.reverse ? '#8854b8' : '#128995', 2.5);
      if (!v.route.reverse) for (const segment of v.route.segments) {
        if (!segment.node_id.startsWith('J_')) continue;
        const visible = v.route.points.filter((point, i) =>
          v.route.arc[i] >= Math.max(segment.start, v.distance - 8) &&
          v.route.arc[i] <= Math.min(segment.end, v.distance + 180));
        drawLine(visible, '#d48714', 3);
      }
    }
    ctx.save();
    ctx.translate(w / 2, h / 2);
    ctx.rotate(-v.pose.heading);
    ctx.fillStyle = '#123e59';
    ctx.fillRect(-12, -6, 24, 12);
    ctx.fillStyle = '#b7e5ef';
    ctx.fillRect(3, -4, 5, 8);
    ctx.restore();
    const shouldMove = !v.paused && v.route && !v.ended && v.target > .1;
    this.stall = shouldMove && moved < .0001 ? this.stall + dt : 0;
    this.longestStall = Math.max(this.longestStall, this.stall);
    if (now - this.lastUI < 100) return;
    this.lastUI = now;
    this.renderUI();
  }
  renderUI() {
    const v = this.vehicle,
      p = this.pipeline,
      row = p.current,
      $ = id => document.getElementById(id);
    $('motionStatus').textContent = motionStatus(v);
    if (row?.phases) $('motionStatus').textContent += ` · Phase ${row.phaseIndex+1}/${row.phases.length}`;
    $('driveMonitor').textContent = `Moving time ${v.movingSeconds.toFixed(1)} s · Distance ${v.totalDistance.toFixed(1)} m · Position (${v.pose.xy.map(x=>x.toFixed(2)).join(', ')}) · Speed ${(v.speed*3.6).toFixed(1)} km/h · Position jumps ${v.jumps} · Layout shifts ${this.layoutShifts} · Longest stall ${this.longestStall.toFixed(1)} s · Last plan ${p.lastLatency.toFixed(0)} ms`;
    const stopped=stopStatus(v.route);
    $('state').textContent = v.paused ? 'Paused' : v.ended ? stopped.title : row ? `${labels[row.status]} · ${row.stage.source_clause}` : v.speed > .05 ? 'Following the road' : 'Ready for an instruction';
    $('detail').textContent = v.paused ? 'Playback is paused. Play resumes from the same position.' : v.ended ? stopped.detail : row?.reason || (v.speed > .05 ? 'The vehicle keeps moving while the next instruction is planned.' : 'Choose a direct command or enter a driving instruction.');
    $('pause').textContent = v.paused ? 'Play' : 'Pause';
    $('pipelineSummary').textContent = row ? `Step ${p.index+1}/${p.rows.length} · ${labels[row.status]||row.status}` + (row.status === 'approaching' ? ` · ${Math.max(0,row.begin-v.distance).toFixed(1)} m to maneuver` : ['waiting', 'planning'].includes(row.status) ? ` · ${Math.max(0,row.timeout-row.waited).toFixed(1)} s left` : '') : `Pipeline finished · ${p.rows.filter(r=>['completed','applied'].includes(r.status)).length}/${p.rows.length} steps completed`;
    $('retryQueue').disabled = $('skipQueue').disabled = !p.blocked;
    const parent = $('pipelineRows');
    while (parent.children.length > p.rows.length) parent.lastChild.remove();
    p.rows.forEach((item, i) => {
      let element = parent.children[i];
      if (!element) {
        element = document.createElement('div');
        parent.append(element);
      }
      element.dataset.stageId = item.id;
      if (i === p.index) element.setAttribute('aria-current','step');
      else element.removeAttribute('aria-current');
      const signature = JSON.stringify([item.stage.source_clause, item.status, item.reason]);
      if (element.dataset.signature === signature) return;
      element.dataset.signature = signature;
      element.className = 'row ' + item.status;
      element.replaceChildren();
      const name = document.createElement('strong');
      name.textContent = `${i+1}. ${item.stage.source_clause}`;
      const status = document.createElement('span');
      status.textContent = labels[item.status] || item.status;
      const reason = document.createElement('small');
      reason.textContent = item.reason || 'Starts when the preceding step finishes or times out.';
      element.append(name, status, reason);
    });
    const focusIndex=Math.min(p.index,p.rows.length-1),focus=parent.children[focusIndex];
    if (focus && $('followQueue').checked) {
      const signature=JSON.stringify([p.generation,focus.dataset.stageId,p.current?.status,parent.scrollHeight,focus.offsetHeight]);
      if (signature!==this.queueFocusSignature) {
        // Scroll only the queue, never the page or map. Manual history browsing
        // remains possible between state transitions, or with follow unchecked.
        parent.scrollTop=Math.max(0,focus.offsetTop-8);
        this.queueFocusSignature=signature;
      }
    }
  }
}
