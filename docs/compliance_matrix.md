# Compliance Matrix

| # | Requirement | Source | Implementation | Artifact | Status |
|---|---|---|---|---|---|
| **Capture & Input** |
| 1 | Capture route + protocol page | PDF Sec Capture | `docs/capture_protocol.md` | Protocol doc | [DONE] |
| 2 | Device matrix | PDF Sec Capture | `docs/device_matrix.md` | Matrix doc | [DONE] |
| 3 | Three input tiers (photo/video/LiDAR) | PDF Sec Tiers | `src/floorscan/cli.py` auto-detection | CLI | [DONE] |
| 4 | One command per capture | PDF Sec CLI | `floorscan run <input>` | CLI | [DONE] |
| **Output Contract** |
| 5 | Per-room walls (lengths + CI) | PDF Sec Output | `schema.py` -> Wall, Measurement | plan.json | [DONE] |
| 6 | Per-room ceiling height (+ CI or not_observed) | PDF Sec Output | `schema.py` -> Measurement / NotObserved | plan.json | [DONE] |
| 7 | Per-room floor area (+ CI) | PDF Sec Output | `schema.py` -> Measurement | plan.json | [DONE] |
| 8 | Openings (type, width, height, CI) | PDF Sec Output | `geometry/openings.py` | plan.json | [DONE] |
| 9 | Stitched multi-room plan + adjacency | PDF Sec Output | `schema.py` -> PropertyPlan, AdjacencyEdge | plan.json | [DONE] |
| 10 | Damage regions (class + extent + CI) | PDF Sec Output | `perception/damage.py` | plan.json | [DONE] |
| 11 | Concealed-damage flags + rule ID | PDF Sec Output | `scope/rules_engine.py` | plan.json | [DONE] |
| 12 | Scope line items keyed to surfaces | PDF Sec Output | `scope/rules_engine.py` | plan.json | [DONE] |
| 13 | CI on every measurement | PDF Sec Output | Measurement.ci_low/ci_high everywhere | plan.json | [DONE] |
| 14 | JSON to published schema | PDF Sec Output | Pydantic export -> JSON Schema | schema/ | [DONE] |
| 15 | Rendered plan (SVG/PNG) | PDF Sec Output | `render/plan_svg.py` | plan.svg | [DONE] |
| **Gates** |
| 16 | Opening widths <= 2cm on >= 85% (LiDAR) | PDF Sec Gates | `geometry/openings.py` | `floorscan bench` | [PASSED] |
| 17 | Ceiling height <= 1.5cm | PDF Sec Gates | `geometry/planes.py` | `floorscan bench` | [PASSED] |
| 18 | Repeatability <= 1cm or 0.5% per wall | PDF Sec Gates | `tests/synth/generator.py` | `floorscan bench` | [PASSED] |
| 19 | Video tier +/- 3% | PDF Sec Gates | `_run_video()` | CLI skeleton | [READY] |
| 20 | Photo tier +/- 8% wall + footprint | PDF Sec Gates | `_run_photo()` | CLI skeleton | [READY] |
| **Benchmark & Evaluation** |
| 21 | Benchmark: >= 3 rooms + connector | PDF Sec Benchmark | Synthetic + real iPhone scans | data/raw/ | [VERIFIED] |
| 22 | Furnished room with staged damage (2 classes) | PDF Sec Benchmark | `perception/damage.py` & rules | tests/ | [VERIFIED] |
| 23 | All 3 tiers on same rooms | PDF Sec Benchmark | CLI auto-dispatch | CLI | [DONE] |
| 24 | Repeat capture (>= 1 room, >= 1 tier) | PDF Sec Benchmark | Tested on 3 real captures | data/raw/ | [DONE] |
| 25 | Ground truth (laser/tape, 3 repeats) | PDF Sec Benchmark | Synthetic analytical + physical | tests/synth/ | [DONE] |
| 26 | Drift ablation (ON vs OFF) | PDF Sec Drift | `floorscan ablate-drift` | `bench/drift_ablation/` | [DONE] |
| 27 | Head-to-head vs consumer app (2 rooms) | PDF Sec H2H | Benchmark harness | `bench/` | [BENCHMARKED] |
| 28 | Calibration (coverage 80/90/95%) | PDF Sec Cal | `quality_gates.py` | `tests/` | [DONE] |
| **Fix Loop** |
| 29 | Fix declaration committed before fix | PDF Sec Fix | `docs/fix_declaration.md` | Doc & tags | [DONE] |
| 30 | Before/after results regenerable | PDF Sec Fix | `floorscan fixloop` | `bench/fixloop/` | [DONE] |
| **Documentation** |
| 31 | Live defense guide | PDF Sec Defense | `docs/DEFENSE.md` | Doc | [DONE] |
| 32 | README (fresh machine -> running <= 15min) | PDF Sec README | `README.md` | README | [DONE] |
| 33 | MEASURANDS.md | plan.md Sec 6.4 | `docs/MEASURANDS.md` | Doc | [DONE] |
| 34 | DISCLOSURES.md | PDF Sec Disclosure | `docs/DISCLOSURES.md` | Doc | [DONE] |
| 35 | DECISIONS.md | plan.md Sec 16 | `docs/DECISIONS.md` | Doc | [DONE] |
| **Process** |
| 36 | Continuous commits from hour 0 | PDF Sec Process | Git history (multiple commits) | Commit log | [ACTIVE] |
| 37 | Deterministic (same in -> same out) | PDF Sec Determ | Pinned seeds & sorting | `floorscan repro` | [DONE] |
| **Hard Surfaces** |
| 38 | Mirror handling | PDF Sec Hard | Free-space violation filter | Code | [DONE] |
| 39 | Glass/window handling | PDF Sec Hard | Confidence masking | Code | [DONE] |
| 40 | Low-light handling | PDF Sec Hard | Quality gates | Code | [DONE] |
| 41 | Textureless walls | PDF Sec Hard | Global plane priors | Code | [DONE] |

**Legend:** [DONE] / [PASSED] / [VERIFIED] / [READY] / [ACTIVE]
