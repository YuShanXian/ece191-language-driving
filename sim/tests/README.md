# Tests

Run the portable fast tier from the repository root:

```powershell
npm --prefix sim test
```

This runs every `unit/*.test.mjs` using Node's built-in test runner, then
`unit/test_contract_geometry.py` using Python's standard-library unittest
runner. No browser, map download, provider request, or MTR output is required.
It uses the Python runtime configured by `ECE191_PYTHON` or the repo `.venv`.
Install [runtime dependencies](../requirements.txt) first. All test output goes
under ignored `sim/tests/results/`.

For an existing read-only WSL environment, set the executable explicitly:

```powershell
$env:ECE191_PYTHON='["wsl.exe","--exec","/path/to/environment/bin/python"]'
npm --prefix sim test
```

The small `fixtures/` files retain state and response geometry for reverse and
multi-phase maneuver regressions. They were extracted from the named historical
development results, not regenerated or treated as new planner results. The
four U-turn/multi-phase fixtures come from `refactor-v35/results/`; the compact
reverse-cusp fixture is the latest matching fixture from the development tree.

## Real-map regressions (optional, slower)

Set `ECE191_DATA_ROOT` or `ECE191_MAP_PATH` as in [DATA.md](../../docs/DATA.md).
Run individual scripts with the configured Python environment, for example:

```powershell
.\.venv\Scripts\python.exe -B sim/tests/unit/engine_regression.py
.\.venv\Scripts\python.exe -B sim/tests/unit/semantic_regression.py
node sim/tests/unit/integration_sequence.mjs
```

The files named `fixtures.py` and `cached_worker.py` now load the current scene
metadata and map; they do not deserialize old app copies. Real-map tests live
in `unit/` because they require no browser, but are excluded from the fast
default command. `route-priority.py` is included through the Python unit tier.

Some historical regressions additionally need excluded recorded inputs:
`lateral_regression.py`, `timeout_regression.py`, `user_regression.py`,
`reverse_geometry_test.py`, `continuation_geometry_test.py`, replay/minimization
scripts, and historical aggregate suites. Their file reads identify the needed
fixtures under `tests/results/`. `human_review_regression.py` requires the
original development review sources under the data root; `parser_replay.py`
needs `results/historical-language/language-results.jsonl`. Do not count these
as executed unless their inputs were supplied. Older aggregate suites remain
historical entry points, not the default acceptance command.

## Browser and replay checks

Start a separate test server on port 8776. With Playwright installed in a local
environment (or exposed through `NODE_PATH`), run:

```powershell
node sim/tests/browser/smoke.cjs
```

It opens a temporary Edge profile inside test results, loads the scene, executes
a direct maneuver, and checks the review subset. Set `ECE191_TEST_URL` to select
another isolated test server and `ECE191_BROWSER_CHANNEL` for another installed
Playwright browser channel. No language service or existing rating store is used.

`browser_gate.py`, `audit_examples.py`, and the physical-destination audits need
`results/browser-run-config.json`, recorded samples, and matching event/request
traces. Their historical expected journeys are not assumed to match a fresh
run. Update the run configuration from the actual recording before auditing.
The `record-*.mjs` modules simulate queue timing without a browser and preserve
their distinct recorder behavior while importing the current app.
`build_review_cases.mjs` and `build_review_maps.py` write only the ignored
`sim/review-data-full/` collection, never the committed review subset.

[SOURCES.md](SOURCES.md) identifies the newest source of each collected test.
One-off probes, source rewriters, and historical report generators are in
`archive/dev-scripts/` and are not test entry points.
