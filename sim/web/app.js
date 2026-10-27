import {
  Vehicle
} from './motion.js';
import {
  Pipeline,
  directStage
} from './pipeline.js';
import {
  View
} from './view.js';
import {DriveClock} from './clock.js';
const $ = selector => document.querySelector(selector);
// The editable combobox only chooses text. Submission stays owned by the form.
const instructionInput = $('#input'), examplePopup = $('#examplePopup');
const exampleOptions = [...document.querySelectorAll('#instructionExamples [role="option"]')];
let activeExample = -1;
function closeExamples() {
  examplePopup.hidden = true;
  instructionInput.setAttribute('aria-expanded', 'false');
  $('#showExamples').setAttribute('aria-expanded', 'false');
  instructionInput.removeAttribute('aria-activedescendant');
  activeExample = -1;
  exampleOptions.forEach(option => option.setAttribute('aria-selected', 'false'));
}
function highlightExample(index) {
  activeExample = index;
  exampleOptions.forEach((option, i) => option.setAttribute('aria-selected', String(i === index)));
  instructionInput.setAttribute('aria-activedescendant', exampleOptions[index].id);
  exampleOptions[index].scrollIntoView({block: 'nearest'});
}
function openExamples() {
  examplePopup.hidden = false;
  instructionInput.setAttribute('aria-expanded', 'true');
  $('#showExamples').setAttribute('aria-expanded', 'true');
  instructionInput.focus({preventScroll: true});
}
function chooseExample(index) {
  instructionInput.value = exampleOptions[index].textContent;
  closeExamples();
  instructionInput.focus({preventScroll: true});
  instructionInput.setSelectionRange(instructionInput.value.length, instructionInput.value.length);
}
$('#showExamples').onclick = () => examplePopup.hidden ? openExamples() : closeExamples();
exampleOptions.forEach((option, index) => {
  option.addEventListener('pointerdown', event => event.preventDefault());
  option.addEventListener('click', () => chooseExample(index));
});
instructionInput.addEventListener('input', closeExamples);
instructionInput.addEventListener('keydown', event => {
  if (event.isComposing) return;
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault();
    if (examplePopup.hidden) openExamples();
    highlightExample(activeExample < 0 ? (event.key === 'ArrowDown' ? 0 : exampleOptions.length - 1) :
      (activeExample + (event.key === 'ArrowDown' ? 1 : -1) + exampleOptions.length) % exampleOptions.length);
  } else if (event.key === 'Enter' && !examplePopup.hidden) {
    event.preventDefault();
    if (activeExample >= 0) chooseExample(activeExample);
    else closeExamples();
  } else if (event.key === 'Escape' || event.key === 'Tab') closeExamples();
});
document.addEventListener('pointerdown', event => {
  if (!event.target.closest('.instruction-combobox')) closeExamples();
});
$('#form').addEventListener('submit', closeExamples);
const preferencesKey = 'ece191-driving-demo.preferences.v1';
let saved = {};
try { saved = JSON.parse(localStorage.getItem(preferencesKey)) || {}; } catch {}
const preferences = {
  speedKmh: typeof saved.speedKmh === 'number' && Number.isFinite(saved.speedKmh) && saved.speedKmh >= 0 && saved.speedKmh <= 54 ? saved.speedKmh : 20,
  waitLimit: [5, 10, 20, 30, 60, 120].includes(saved.waitLimit) ? saved.waitLimit : 20,
  scene: Number.isInteger(saved.scene) && saved.scene >= 1 && saved.scene <= 7 ? saved.scene : 1,
  queueMode: saved.queueMode === 'replace' ? 'replace' : 'append',
  followQueue: typeof saved.followQueue === 'boolean' ? saved.followQueue : true,
  modelId: typeof saved.modelId === 'string' ? saved.modelId : null
};
function savePreferences(changes) {
  Object.assign(preferences, changes);
  try { localStorage.setItem(preferencesKey, JSON.stringify(preferences)); } catch {}
}
$('#speedTarget').value = preferences.speedKmh;
$('#waitLimit').value = preferences.waitLimit;
$('#scene').value = preferences.scene;
$('#queueMode').value = preferences.queueMode;
$('#followQueue').checked = preferences.followQueue;
async function post(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  });
  const result = await r.json();
  if (!r.ok) throw Error(result.error || 'Request failed');
  return result;
}
const vehicle = new Vehicle();
const sessionId = crypto.randomUUID();
const pipeline = new Pipeline(vehicle, body => post('/api/plan', body), event => {
  if (['applied', 'completed'].includes(event.type) && ['set_speed', 'speed_up', 'slow_down'].includes(event.action)) rememberSpeed();
  void post('/api/events', {...event, session_id: sessionId, client_release: 'v40'}).catch(() => {});
});
function rememberSpeed() {
  const speedKmh = Number((vehicle.target * 3.6).toFixed(3));
  $('#speedTarget').value = speedKmh;
  savePreferences({speedKmh});
}
const view = new View(vehicle, pipeline);
let ready = false,
  sceneEpoch = 0,
  parsing = false;

function enqueue(stages) {
  if (!ready) {
    $('#reply').textContent = 'The map is still loading.';
    return;
  }
  if (stages.length === 1 && ['cancel', 'emergency_stop'].includes(stages[0].action)) {
    cancelQueue();
    return;
  }
  pipeline.add(stages, {
    replace: $('#queueMode').value === 'replace',
    timeout: Number($('#waitLimit').value)
  });
  $('#reply').textContent = 'Instruction added. The vehicle continues while the route is checked.';
}

function cancelQueue() {
  pipeline.cancel();
  $('#reply').textContent = 'Queue cancelled. Any pending language response will be discarded.';
}
async function loadScene() {
  const epoch = ++sceneEpoch,
    scene = Number($('#scene').value);
  ready = false;
  pipeline.reset(scene);
  vehicle.reset();
  vehicle.target = preferences.speedKmh / 3.6;
  view.setRoads([]);
  view.layoutShifts = 0;
  view.longestStall = 0;
  $('#loading').textContent = 'Loading this map once…';
  $('#reply').textContent = 'Preparing scene geometry';
  try {
    const r = await fetch('/api/scene?scene=' + scene);
    const data = await r.json();
    if (!r.ok) throw Error(data.error);
    if (epoch !== sceneEpoch) return;
    view.setRoads(data.roads);
    vehicle.reset(data.start);
    vehicle.target = preferences.speedKmh / 3.6;
    ready = true;
    $('#loading').textContent = 'Map ready';
    $('#reply').textContent = 'Ready. New commands do not pause existing motion.';
  } catch (error) {
    if (epoch === sceneEpoch) {
      $('#loading').textContent = 'Map unavailable';
      $('#reply').textContent = error.message;
    }
  }
}
document.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', () => enqueue([directStage(button.dataset.action)])));
$('#scene').onchange = () => { savePreferences({scene: Number($('#scene').value)}); void loadScene(); };
$('#waitLimit').onchange = () => savePreferences({waitLimit: Number($('#waitLimit').value)});
$('#queueMode').onchange = () => savePreferences({queueMode: $('#queueMode').value});
$('#followQueue').addEventListener('change', () => savePreferences({followQueue: $('#followQueue').checked}));
$('#modelSelect').onchange = () => savePreferences({modelId: $('#modelSelect').value});
$('#resetScene').onclick = loadScene;
$('#pause').onclick = () => {
  vehicle.paused = !vehicle.paused;
  pipeline.emit('playback_changed',{paused:vehicle.paused});
};
$('#cancelQueue').onclick = cancelQueue;
$('#retryQueue').onclick = () => {
  const row = pipeline.current;
  if (row?.stage.action === 'parse' && pipeline.blocked && !parsing) {
    row.status = 'parsing';
    row.waited = 0;
    row.reason = 'Retrying language parsing in the original queue position.';
    void parseLanguage(row, row.stage.source_clause);
  } else pipeline.retry(Number($('#waitLimit').value));
};
$('#skipQueue').onclick = () => pipeline.skip();
$('#slower').onclick = () => {
  vehicle.target = Math.max(0, vehicle.target - 2);
  rememberSpeed();
};
$('#faster').onclick = () => {
  vehicle.target = Math.min(15, vehicle.target + 2);
  rememberSpeed();
};
$('#applySpeed').onclick = () => {
  const speed = Number($('#speedTarget').value);
  if ($('#speedTarget').value.trim() && Number.isFinite(speed) && speed >= 0 && speed <= 54) {
    vehicle.target = speed / 3.6;
    rememberSpeed();
  }
};
$('#stopLive').onclick = cancelQueue;
$('#form').onsubmit = async event => {
  event.preventDefault();
  if (parsing || !ready) return;
  const instruction = $('#input').value.trim();
  if (!instruction) return;
  const row = pipeline.reserveLanguage(instruction, {
    replace: $('#queueMode').value === 'replace',
    timeout: Number($('#waitLimit').value)
  });
  await parseLanguage(row, instruction);
};
async function parseLanguage(row, instruction) {
  const epoch = sceneEpoch;
  parsing = true;
  $('#send').disabled = true;
  $('#reply').textContent = 'Parsing the instruction. Driving continues; later commands keep their queue order.';
  try {
    const plan = await post('/api/parse', {
      instruction,
      model: $('#modelSelect').value
    });
    if (epoch !== sceneEpoch || row.status !== 'parsing') return;
    const accepted = pipeline.resolveLanguage(row, plan);
    $('#reply').textContent = accepted ? 'Parsed and queued in the original order.' : row.reason;
  } catch (error) {
    if (epoch === sceneEpoch && row.status === 'parsing') {
      row.status = 'error';
      row.reason = error.message;
      $('#reply').textContent = error.message;
    }
  } finally {
    parsing = false;
    $('#send').disabled = false;
  }
}
$('#history').ontoggle = async () => {
  if ($('#history').open) {
    try {
      $('#historyRows').textContent = JSON.stringify(await (await fetch('/api/history')).json(), null, 2);
    } catch {}
  }
};
async function health() {
  try {
    const response = await fetch('/health');
    const data = await response.json();
    $('#connection').textContent = response.ok ? 'Service connected' : 'Service unavailable';
  } catch {
    $('#connection').textContent = 'Service reconnecting…';
  }
}
fetch('/api/models').then(r => r.json()).then(data => {
  const enabled = data.models.filter(x => x.enabled);
  const selected = enabled.some(x => x.id === preferences.modelId) ? preferences.modelId : data.default;
  for (const model of enabled) {
    const option = document.createElement('option');
    option.value = model.id;
    option.textContent = model.label || model.name || model.id;
    option.selected = model.id === selected;
    $('#modelSelect').append(option);
  }
}).catch(() => {});
const driveClock = new DriveClock(performance.now());

function advance(now) {
  const {dt, moved} = driveClock.advance(now, vehicle, pipeline, ready);
  view.render(now, dt, moved);
}
function frame(now) {
  advance(now);
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
// A background animation frame is not a reliable simulation heartbeat.
setInterval(() => advance(performance.now()), 100);
void health();
setInterval(health, 10000);
// Audit motion even after the last queued action completes. A moving car alone
// is not proof that its pending instruction or later continuation is correct.
setInterval(() => {
  if (!ready || vehicle.paused || !vehicle.route) return;
  pipeline.emit('telemetry', {moving_seconds:vehicle.movingSeconds, distance_m:vehicle.totalDistance,
    route_distance_m:vehicle.distance, ended:vehicle.ended, position_jumps:vehicle.jumps,
    stop_context:vehicle.route.stopContext,
    max_heading_step:vehicle.maxHeadingStep, layout_shifts:view.layoutShifts, longest_stall:view.longestStall,
    current_movement:vehicle.route.movements.find(m=>vehicle.distance>=m.start && vehicle.distance<m.end) || null,
    phase:pipeline.current?.status || 'continuation'});
}, 5000);
void loadScene();
