# Data and external resources

nuPlan supplies vector road maps and recorded vehicle states/history. doPlan
supplies language annotations associated with recorded driving windows. A
window boundary is not necessarily the time a passenger spoke; recorded futures
are not ground truth for every alternative route a passenger could request.

Obtain nuPlan through its [official project](https://www.nuscenes.org/nuplan)
and [devkit](https://github.com/motional/nuplan-devkit). Follow its dataset terms.
The historical `RESOURCE_ORIGINS.txt` points to the
[doPlan repository](https://github.com/Mi3-Lab/doPlan) and
[paper](https://arxiv.org/html/2609.38028v1). Its UC Merced video/GPS share is a
separate viewing resource, not the raw nuPlan database or map package. Private
sharing details are deliberately excluded here.

Place the downloaded map at:

```text
data/nuplan/maps/us-nv-las-vegas-strip/9.15.1915/map.gpkg
```

`ECE191_DATA_ROOT` can point to an external project directory containing
`data/nuplan/maps/...`; it defaults to this repository root. `ECE191_MAP_PATH`
can instead identify the map directly. The planning map is not committed.

`sim/data/scenes/sceneNN.json` contains only the origin, projection, initial pose,
relative map location, and source identifiers needed to recreate each scene.
`sim/tools/export_scenes.py --source-root PATH` extracts these from historical
conversion and inference files. The server never reads those historical files.
The extraction is an offline migration tool, not an MTR runtime dependency.

`sim/review-data/` contains the six `v40-browser-example-*` recordings listed in
its catalog and their required map snapshot. They are interpolated checkpoints,
not videos. Source fingerprints retain their original meaning; path labels are
made relative for publication. Other historical replays were not copied. If
needed locally, place them in ignored `sim/review-data-full/` and select that
directory with `ECE191_REVIEW_DATA_ROOT`.

Raw databases, sensor recordings, full maps, model weights, third-party source
trees, converted samples, experiment outputs, installers, and provider settings
are excluded. The MIT license covers project code; it does not relicense nuPlan,
doPlan, or other upstream material.
