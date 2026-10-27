"""Persistent JSON-lines planner. Scene geometry is loaded once per worker."""

import json, sys, time, traceback, contextlib
from engine.scene import get_scene
from engine.planner import plan
from engine.normalize import normalize
from engine.contract import validate

for line in sys.stdin:
    request = {}
    try:
        request = json.loads(line)
        started = time.perf_counter()
        with contextlib.redirect_stdout(sys.stderr):
            op = request.get("op")
            if op == "scene":
                scene = get_scene(int(request["scene"]))
                result = {
                    "scene": scene.number,
                    "roads": scene.roads,
                    "start": {"xy": [0, 0], "heading": 0, "speed": 0},
                    "node_count": len(scene.nodes),
                }
            elif op == "normalize":
                # Provider timing is transport metadata, not part of the instruction contract.
                value = dict(request["plan"])
                metadata = value.pop("model_info", None)
                validate(value)
                result = normalize(value)
                if metadata is not None:
                    result["model_info"] = metadata
            else:
                result = plan(request)
        print(
            json.dumps(
                {
                    "id": request["id"],
                    "result": result,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                },
                separators=(",", ":"),
            ),
            flush=True,
        )
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"id": request.get("id"), "error": str(e)}), flush=True)
