const held = new Set(['blocked', 'unsupported', 'error']);
const controls = new Set(['set_speed', 'speed_up', 'slow_down', 'stop', 'hold_stopped', 'emergency_stop', 'cancel']);
export function directStage(action) {
  const extreme = {leftmost_lane:'leftmost',rightmost_lane:'rightmost'}[action];
  return {
    action: extreme ? 'select_lane' : action,
    source_clause: extreme ? `move to the ${extreme} lane` : action.replaceAll('_', ' '),
    trigger: 'now',
    trigger_text: '',
    trigger_value: null,
    target_text: '',
    lane_reference: extreme || 'none',
    lane_number: extreme ? 1 : null,
    completion_text: '',
    constraints: [],
    travel_distance_m: action === 'reverse' ? 10 : null,
    stop_at_end: action === 'reverse',
    target_speed_mps: null
  };
}

export class Pipeline {
  constructor(vehicle, request, onEvent = () => {}) {
    this.vehicle = vehicle;
    this.request = request;
    this.onEvent = onEvent;
    this.rows = [];
    this.index = 0;
    this.generation = 0;
    this.pending = false;
    this.serial = 0;
    this.scene = 1;
    this.lastLatency = 0;
    this.maxLatency = 0;
  }
  get current() {
    return this.rows[this.index];
  }
  get blocked() {
    return held.has(this.current?.status);
  }
  emit(type, extra = {}) {
    const {
      history,
      ...state
    } = this.vehicle.state();
    this.onEvent({
      type,
      scene: this.scene,
      stage_id: this.current?.id,
      action: this.current?.stage.action,
      state,
      ...extra
    });
  }
  add(stages, {
    replace = false,
    timeout = 20
  } = {}) {
    if (stages.length === 1 && ['cancel', 'emergency_stop'].includes(stages[0].action)) {
      this.cancel();
      return;
    }
    if (replace) {
      const committed = ['approaching', 'executing', 'stopping', 'braking_reverse', 'braking_maneuver'].includes(this.current?.status);
      if (committed) {
        this.rows.splice(this.index + 1);
      } else {
        this.generation++;
        this.pending = false;
        for (let i = this.index; i < this.rows.length; i++) this.rows[i].status = 'cancelled';
        this.index = this.rows.length;
      }
    }
    const newRows = stages.map(stage => ({
      id: ++this.serial,
      stage,
      status: 'queued',
      waited: 0,
      timeout,
      reason: '',
      attempts: 0,
      retryAt: 0
    }));
    if ((this.blocked || this.vehicle.ended) && newRows.length === 1 && ['reverse', 'reverse_continuous'].includes(newRows[0].stage.action)) this.rows.splice(this.index, 0, ...newRows);
    else this.rows.push(...newRows);
    this.emit('queued', {
      stages, added_stage_ids: newRows.map(r=>r.id), queue_mode: replace?'replace':'append', timeout
    });
    return newRows;
  }
  reserveLanguage(text, options) {
    const [row] = this.add([{
      action: 'parse',
      source_clause: text
    }], options);
    row.status = 'parsing';
    row.reason = 'Parsing language while current road following continues.';
    return row;
  }
  resolveLanguage(row, plan) {
    const index = this.rows.indexOf(row);
    if (index < 0 || row.status !== 'parsing') return false;
    if (plan.status !== 'parsed' || plan.unresolved_text?.length || !plan.stages?.length) {
      row.status = 'unsupported';
      row.reason = plan.explanation || 'Please clarify the instruction.';
      return false;
    }
    const rows = plan.stages.map((stage, i) => ({
      ...row,
      id: i ? ++this.serial : row.id,
      stage,
      status: 'queued',
      reason: '',
      waited: 0
    }));
    this.rows.splice(index, 1, ...rows);
    return true;
  }
  reset(scene) {
    this.generation++;
    this.pending = false;
    this.rows = [];
    this.index = 0;
    this.scene = scene;
    this.lastLatency = 0;
    this.maxLatency = 0;
  }
  cancel() {
    const cancelled = this.rows.slice(this.index).map(r=>({id:r.id,action:r.stage.action,status:r.status}));
    this.generation++;
    this.pending = false;
    for (let i = this.index; i < this.rows.length; i++) this.rows[i].status = 'cancelled';
    this.index = this.rows.length;
    this.vehicle.stop(true);
    this.vehicle.route = null;
    this.vehicle.epoch++;
    this.vehicle.ended = false;
    this.emit('cancelled',{stage_id:cancelled[0]?.id,action:cancelled[0]?.action,cancelled_stages:cancelled});
  }
  complete(status = 'completed') {
    const row = this.current;
    if (!row) return;
    row.status = status;
    this.emit(status, {
      reason: row.reason,
      waited: row.waited,
      request_id: row.requestId,
      route_source: row.routeSource,
      phases: row.phaseExecutions || [],
      journey: row.journey,
      execution: row.execution ? {
        ...row.execution,
        finish: this.vehicle.state().xy,
        finish_heading: this.vehicle.pose.heading,
        finish_node: this.vehicle.state().node_id,
        distance: this.vehicle.totalDistance - row.execution.start_distance
      } : null
    });
    this.index++;
  }
  retry(timeout) {
    if (!this.blocked) return;
    Object.assign(this.current, {
      status: 'queued',
      waited: 0,
      timeout,
      reason: '',
      retryAt: 0
    });
  }
  skip() {
    if (this.blocked) this.complete('skipped');
  }
  localControl(stage) {
    const v = this.vehicle,
      a = stage.action;
    if (a === 'set_speed') v.target = Math.max(0, Math.min(15, stage.target_speed_mps ?? v.target));
    if (a === 'speed_up') v.target = Math.min(15, v.target + (stage.speed_delta_mps ?? 2));
    if (a === 'slow_down') v.target = Math.max(0, v.target - (stage.speed_delta_mps ?? 2));
    if (['stop', 'hold_stopped'].includes(a)) v.stop();
    if (a === 'resume' || a === 'continuous_drive') {
      if (v.target <= 0) v.target = 20 / 3.6;
      v.paused = false;
    }
  }
  tick(dt) {
    const row = this.current,
      v = this.vehicle;
    if (!row || v.paused || this.blocked || row.status === 'parsing') return;
    if (!row.journey) {
      row.journey = {origin: {...v.pose, xy: [...v.pose.xy]}, start_distance: v.totalDistance,
        samples: [], visited_nodes: [], observed_movements: [], last_sample_distance: -Infinity};
      this.emit('activated');
    }
    this.observe(row);
    if (['planning', 'waiting'].includes(row.status)) row.waited += dt;
    if (['planning', 'waiting'].includes(row.status) && row.waited >= row.timeout) {
      this.generation++;
      this.pending = false;
      row.reason = `Not executed within the waiting limit: ${row.reason || 'No executable route found.'} Continuing with the next instruction.`;
      this.complete('timed_out');
      return;
    }
    if (row.status === 'approaching' && v.distance >= row.begin) {
      row.status = 'executing';
      this.emit('executing');
    }
    if (['executing', 'approaching'].includes(row.status)) {
      if (row.execution) {
        const nodes = row.execution.visited_nodes;
        if (v.pose.node_id && nodes.at(-1) !== v.pose.node_id) nodes.push(v.pose.node_id);
        if (!row.execution.entry && v.distance >= row.begin) {
          row.execution.entry = {xy: [...v.pose.xy], heading: v.pose.heading, node_id: v.pose.node_id};
        }
      }
      if (v.distance >= row.completion - .02) {
        if ((row.stage.stop_at_end || row.waitForStop || v.route?.reverse) && !v.ended) return;
        if (row.phases) {
          row.phaseExecutions.push({index:row.phaseIndex,reverse:v.route.reverse,
            expected_finish:row.execution.expected_finish,finish:v.state(),
            journey_distance:v.totalDistance-row.execution.start_distance});
          this.emit('phase_completed',{phase:row.phaseIndex,request_id:row.requestId});
          if (row.phaseIndex+1 < row.phases.length) {
            if (v.speed>.02 || !v.ended) {
              row.status='error';row.reason='A gear change requires a complete stop.';
              this.emit('error',{reason:row.reason});return;
            }
            const next=row.phases[++row.phaseIndex];
            if (!this.startPhase(row,next,route=>v.install(route,{maxAdvance:.5,speedCap:next.speed_limit_mps||15}))) {
              row.status='error';row.reason='The next maneuver phase does not meet the stopped vehicle pose.';
              this.emit('error',{reason:row.reason});
            }
            return;
          }
          v.speedCap=15;
        }
        this.complete();
      }
      return;
    }
    if (row.status === 'stopping') {
      if (v.speed < .02) this.complete();
      return;
    }
    if (row.status === 'braking_reverse') {
      if (v.speed >= .02) return;
      row.status = 'queued';
      row.reverseBraked = true;
    }
    if (row.status === 'braking_maneuver') {
      if (v.speed >= .02) return;
      row.status='queued';
    }
    // A safe stop at a junction is still waiting, not a permanent queue block.
    if (this.pending || (v.totalDistance < row.retryAt && row.waited < (row.retryTime ?? Infinity))) return;
    if (['reverse', 'reverse_continuous'].includes(row.stage.action) && !row.reverseBraked && v.speed > .02) {
      row.resumeTarget=v.target>0?v.target:20/3.6;
      v.stop();
      row.status = 'braking_reverse';
      row.reason = 'Stopping before reversing along the current lane.';
      this.emit('braking_reverse');
      return;
    }
    if (controls.has(row.stage.action) && !row.stage.constraints?.length && !row.stage.target_text && ['now', 'after_previous'].includes(row.stage.trigger)) {
      this.localControl(row.stage);
      row.reason = 'Control applied without a planner round trip.';
      if (['stop', 'hold_stopped'].includes(row.stage.action) && v.speed > .02) row.status = 'stopping';
      else this.complete('applied');
      return;
    }
    void this.plan(row);
  }
  startPhase(row, phase, install) {
    const v=this.vehicle;
    if (!install(phase.route)) return false;
    row.begin=phase.maneuver_start_m||0;
    row.completion=phase.completion_m??v.route.length;
    row.waitForStop=!!phase.stop_at_end;
    row.reason=phase.reason||row.reason;
    row.execution={start:[...v.pose.xy],start_heading:v.pose.heading,start_distance:v.totalDistance,
      begin:row.begin,completion:row.completion,visited_nodes:[],
      segments:phase.route.segments.filter(s=>s.start<=row.completion),expected_finish:v.route.at(row.completion)};
    row.status=v.distance<row.begin?'approaching':'executing';
    if (phase.target_speed_mps!=null)v.target=phase.target_speed_mps;
    if (v.target<=0)v.target=row.resumeTarget||20/3.6;
    this.emit('route_installed',{request_id:row.requestId,latency_ms:this.lastLatency,
      begin:row.begin,completion:row.completion,phase:row.phaseIndex,phase_count:row.phases?.length,
      reverse:v.route.reverse,preparation:phase.route.preparation});
    return true;
  }
  observe(row) {
    const v = this.vehicle, trace = row.journey;
    const node = v.pose.node_id;
    if (node && trace.visited_nodes.at(-1) !== node) trace.visited_nodes.push(node);
    for (const movement of v.route?.movements || []) {
      if (v.distance >= movement.start && v.distance < movement.end &&
          !trace.observed_movements.some(x => x.connector === movement.connector)) {
        trace.observed_movements.push({...movement, phase: row.status, xy: [...v.pose.xy], heading: v.pose.heading});
      }
    }
    if (v.totalDistance - trace.last_sample_distance >= 2 || trace.samples.length === 0) {
      trace.samples.push({xy: [...v.pose.xy], heading: v.pose.heading, node_id: node,
        phase: row.status, distance: v.totalDistance - trace.start_distance});
      trace.last_sample_distance = v.totalDistance;
    }
  }
  async plan(row) {
    const generation = this.generation,
      v = this.vehicle,
      epoch = v.epoch,
      state = v.state(),
      distanceBefore = v.totalDistance,
      started = performance.now();
    row.status = 'planning';
    row.attempts++;
    this.pending = true;
    try {
      const response = await this.request({
        scene: this.scene,
        state,
        stage: row.stage,
        remaining: Math.max(0, row.timeout - row.waited),
        elapsed: row.waited
      });
      if (generation !== this.generation || this.current !== row) return;
      this.lastLatency = performance.now() - started;
      this.maxLatency = Math.max(this.maxLatency, this.lastLatency);
      row.requestId = response.request_id;
      if (epoch !== v.epoch) {
        row.status = 'waiting';
        row.retryAt = v.totalDistance;
        row.retryTime = row.waited + 1;
        row.reason = 'Vehicle route changed; replanning from its current position.';
        return;
      }
      row.reason = response.reason || '';
      const install = route => v.install(route, {
        maxAdvance: Math.max(5, v.totalDistance - distanceBefore + 5),
        speedCap: response.speed_limit_mps || 15
      });
      if (response.status === 'ready') {
        row.phases=response.phases;
        row.phaseIndex=0;
        row.phaseExecutions=[];
        row.routeSource=response.route_source;
        const phase=row.phases?.[0]||response;
        if (row.phases?.slice(0,-1).some(p=>!p.stop_at_end||Math.abs(p.completion_m-p.route.length)>.02))
          throw Error('Intermediate maneuver phases must stop at their route endpoint');
        if (!this.startPhase(row,phase,install)) {
          row.status = 'waiting';
          row.reason = 'The car passed the planned entry; checking the next connected opportunity.';
          row.retryAt = v.totalDistance + 1;
          row.retryTime = row.waited + 1;
          return;
        }
      } else if (response.status === 'braking') {
        row.resumeTarget=v.target>0?v.target:20/3.6;
        v.stop();
        row.status='braking_maneuver';
        this.emit('braking_maneuver',{reason:row.reason});
      } else if (response.status === 'waiting') {
        // The neutral route is a constraint, never keep an old turning tail.
        if (response.route && install(response.route) && v.target <= 0)
          v.target = row.resumeTarget || 20 / 3.6;
        row.status = 'waiting';
        row.retryAt = v.totalDistance + (response.retry_after_m || 5);
        row.retryTime = row.waited + (response.retry_after_s || 1);
        this.emit('waiting', {
          request_id: row.requestId,
          reason: row.reason,
          latency_ms: this.lastLatency
        });
      } else if (response.status === 'control') {
        if (response.route && !install(response.route)) {
          row.status = 'waiting';
          row.retryAt = v.totalDistance + 1;
          row.retryTime = row.waited + 1;
          return;
        }
        this.localControl(response.control);
        row.reason = response.reason || 'Road-following control applied.';
        this.complete('applied');
      } else {
        row.status = response.status;
        this.emit(response.status, {
          reason: row.reason,
          request_id: row.requestId
        });
      }
    } catch (error) {
      if (generation === this.generation && this.current === row) {
        row.status = 'error';
        row.reason = error.message;
        this.emit('error', {
          reason: error.message
        });
      }
    } finally {
      if (generation === this.generation) this.pending = false;
    }
  }
}
