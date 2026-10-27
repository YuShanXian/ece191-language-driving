# Language-guided driving simulation

Release `0.40.0` (v40), copied from the deployed application. It uses map geometry
and a stateful browser instruction queue. It does not model traffic or physics.

From the repository root, install Node.js and create a Python environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r sim/requirements.txt
node sim/server.cjs
```

On Linux/macOS, use `.venv/bin/python` in the install command. Node uses only
built-in runtime modules; no npm install is needed to serve the app or run its
JavaScript unit tests. Python dependencies come from engine imports and the
historical runtime requirements; training dependencies are excluded.

Put the planning map at the location in [DATA.md](../docs/DATA.md). Open
<http://localhost:8775> and choose a scene. Try **Go straight**, then **Stop**.
**Reset scene** explicitly returns to the scene origin. New commands otherwise
use the current state. Queue controls choose whether new instructions append or
replace pending work. If that port is occupied, set `$env:DEMO_PORT='8776'` before
starting. The service binds locally. Stop your own server with Ctrl+C.

The `/review` page reads the bundled replay subset and map snapshot without the
external planning map or an LLM. New scores are saved locally in `logs/reviews/`.

Free text uses a configured provider CLI. The copied model catalog records the
development configuration; it does not guarantee provider access or current
model availability. Update the local catalog as needed. Configure the provider
separately and expose its executable on PATH or use an environment variable.
Provider state is not included. Direct buttons work without a provider. Parser
responses use the engine schema and preserve unsupported conditions instead of
pretending to execute them.

| Setting | Default / purpose |
|---|---|
| `DEMO_PORT` | `8775`; choose another port for a second instance |
| `ECE191_PYTHON` | Repo `.venv` Python, falling back to Python on PATH |
| `ECE191_DATA_ROOT` | Repo root; contains `data/nuplan/maps/...` |
| `ECE191_MAP_PATH` | Optional map path, relative to data root |
| `ECE191_SCENES_ROOT` | `sim/data/scenes`, relative to repo root |
| `DEMO_TRACE_ROOT` | `logs`, relative to repo root |
| `ECE191_REVIEW_ROOT` | `logs/reviews`, independent of data root |
| `ECE191_REVIEW_DATA_ROOT` | `sim/review-data` |
| `ECE191_PARSER_PROMPT` | `sim/parser/prompt.txt` |
| `ECE191_CODEX`, `ECE191_CLAUDE`, `ECE191_GEMINI`, `ECE191_AGY` | Provider executable on PATH |

Copy [`.env.example`](../.env.example) to `.env`, then use
`node --env-file=.env sim/server.cjs`, or set variables in your shell.
WSL is optional: `ECE191_PYTHON` accepts a JSON argv array such as
`["wsl.exe","--exec","/path/to/environment/bin/python"]`.
The launcher translates Windows paths and forwards configuration to WSL.
With WSL, provider CLIs must also be available in that Linux environment.

| Files | Responsibility |
|---|---|
| `server.cjs`, `runtime.cjs` | HTTP routes, configuration, Python launch |
| `worker-client.cjs`, `worker.py` | Persistent planner process and request queue |
| `engine/scene.py`, `map_data.py`, `topology.py` | Scene transforms, map and lane graph |
| `engine/planner.py`, maneuver modules | Connected routes, search and geometry checks |
| `engine/schema.json`, `contract.py`, `normalize.py` | Single action contract and validation |
| `parser/` | Prompt, model catalog, CLI adapter and semantic cleanup |
| `web/` | Instruction queue, timed motion, drawing and controls |
| `review-*.cjs`, `review-data/` | Local review API, persistence and examples |
| `data/scenes/`, `tools/export_scenes.py` | Scene metadata and offline extractor |
| `tests/` | Unit tests, optional map regressions and browser gates |

Run `npm --prefix sim test`. See [tests/README.md](tests/README.md) for the full
verification workflow and external prerequisites.