# Historical source reference

Yushan's earlier nuPlan-to-MTR conversion, inference and candidate-selection
attempt was abandoned for her own track. Doh's parallel MTR selection approach
remains active as a team proposal; this archive is not his implementation.

| Folder | Contents and reason retained | Original location |
|---|---|---|
| `mtr-baseline/` | Conversion, pretrained inference, candidate tools, `mtr_project/`, and compatibility patch; earlier Yushan baseline | `D:\ECE191-MTR\scripts`; patch from `config/upstream-compatibility.patch` |
| `research-scripts/` | Historical controllers, tracking, alignment, reports, old servers and related utilities; outside the current app dependency graph | Same source `scripts/` tree |
| `dev-scripts/` | Latest one-off probes, diagnostics, source rewriters and report generators; development history, not test entry points | Historical class workspace, `ece191-development/refactor-v*/tests/` |
| `old-docs/` | English archival digests of every source `.txt` research note, with original content fingerprints | Source project `docs/*.txt` |

Before copying, source module/file references were checked against the current
sim and collected tests. The active external dependencies were
`parser_backends.py` and `semantic_contract_v21.py`; both are now in `sim/parser/`
and excluded here. The current app does not import `mtr_project` or another
archived module. A shared basename such as `planner.py` does not mean the old
MTR module is the current engine module.

These are publication copies, not a byte-identical backup or an executable
reproduction bundle. Machine-specific paths and private links/contact details
were replaced with neutral historical labels. Some old identifier spellings
were normalized for publication. Non-English fixture strings remain represented
as Unicode escapes where needed to retain source behavior; non-English comments
are annotated in English. Original source files remain unchanged.

The `.txt` notes are explicitly **abridged English editions**, not verbatim
translations. They retain purpose, findings, evidence references and limits,
while omitting personal account operations and private discussion details.
Each identifies its original file and SHA-256. Historical counts in those notes
are not new measurements from this repository.

Only source code, the compatibility patch and documentation are retained.
No old app folder copies, datasets, weights, experiment outputs, installers or
compressed bundles are included. Historical launchers, installers and cleanup
utilities are retained as source references and are not part of setup or tests.
Reproducing old experiments requires restoring their external inputs and
reviewing the publication edits; do not run these scripts as the current demo.

Use [the current app](../sim/README.md) for the design review and
[the test guide](../sim/tests/README.md) for verification.
