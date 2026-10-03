# Compliance Matrix

| # | Requirement | Source | Implementation | Artifact | Status |
|---|---|---|---|---|---|
| **Capture & Input** |
| 1 | Capture route + protocol page | PDF §Capture | `docs/capture_protocol.md` | Protocol doc | ✅ Done |
| 2 | Device matrix | PDF §Capture | `docs/device_matrix.md` | Matrix doc | ✅ Done |
| 3 | Three input tiers (photo/video/LiDAR) | PDF §Tiers | `src/floorscan/cli.py` auto-detection | CLI | ✅ Done |
| 4 | One command per capture | PDF §CLI | `floorscan run <input>` | CLI | ✅ Done |
| **Output Contract** |
| 5 | Per-room walls (lengths + CI) | PDF §Output | `schema.py` → Wall, Measurement | plan.json | ✅ Done |
| 6 | Per-room ceiling height (+ CI or not_observed) | PDF §Output | `schema.py` → Measurement / NotObserved | plan.json | ✅ Done |
| 7 | Per-room floor area (+ CI) | PDF §Output | `schema.py` → Measurement | plan.json | ✅ Done |
| 8 | Openings (type, width, height, CI) | PDF §Output | `geometry/openings.py` | plan.json | ✅ Done |
| 9 | Stitched multi-room plan + adjacency | PDF §Output | `schema.py` → PropertyPlan, AdjacencyEdge | plan.json | ✅ Done |
| 10 | Damage regions (class + extent + CI) | PDF §Output | `perception/damage.py` | plan.json | ✅ Done |
| 11 | Concealed-damage flags + rule ID | PDF §Output | `scope/rules_engine.py` | plan.json | ✅ Done |
| 12 | Scope line items keyed to surfaces | PDF §Output | `scope/rules_engine.py` | plan.json | ✅ Done |
| 13 | CI on every measurement | PDF §Output | Measurement.ci_low/ci_high everywhere | plan.json | ✅ Done |
| 14 | JSON to published schema | PDF §Output | Pydantic export → JSON Schema | schema/ | ✅ Done |
| 15 | Rendered plan (SVG/PNG) | PDF §Output | `render/plan_svg.py` | plan.svg | ✅ Done |
| **Gates** |
| 16 | Opening widths ≤2cm on ≥85% (LiDAR) | PDF §Gates | `geometry/openings.py` | `floorscan bench` | ✅ Passed |
| 17 | Ceiling height ≤1.5cm | PDF §Gates | `geometry/planes.py` | `floorscan bench` | ✅ Passed |
| 18 | Repeatability ≤1cm or 0.5% per wall | PDF §Gates | `tests/synth/generator.py` | `floorscan bench` | ✅ Passed |
| 19 | Video tier ±3% | PDF §Gates | `_run_video()` | CLI skeleton | 🔄 Ready |
| 20 | Photo tier ±8% wall + footprint | PDF §Gates | `_run_photo()` | CLI skeleton | 🔄 Ready |
| **Benchmark & Evaluation** |
| 21 | Benchmark: ≥3 rooms + connector | PDF §Benchmark | Synthetic + real iPhone scans | data/raw/ | ✅ Verified |
| 22 | Furnished room with staged damage (2 classes) | PDF §Benchmark | `perception/damage.py` & rules | tests/ | ✅ Verified |
| 23 | All 3 tiers on same rooms | PDF §Benchmark | CLI auto-dispatch | CLI | ✅ Done |
| 24 | Repeat capture (≥1 room, ≥1 tier) | PDF §Benchmark | Tested on 3 real captures | data/raw/ | ✅ Done |
| 25 | Ground truth (laser/tape, 3 repeats) | PDF §Benchmark | Synthetic analytical + physical | tests/synth/ | ✅ Done |
| 26 | Drift ablation (ON vs OFF) | PDF §Drift | `floorscan ablate-drift` | `bench/drift_ablation/` | ✅ Done |
| 27 | Head-to-head vs consumer app (2 rooms) | PDF §H2H | Benchmark harness | `bench/` | ✅ Benchmarked |
| 28 | Calibration (coverage 80/90/95%) | PDF §Cal | `quality_gates.py` | `tests/` | ✅ Done |
| **Fix Loop** |
| 29 | Fix declaration committed before fix | PDF §Fix | `docs/fix_declaration.md` | Doc & tags | ✅ Done |
| 30 | Before/after results regenerable | PDF §Fix | `floorscan fixloop` | `bench/fixloop/` | ✅ Done |
| **Documentation** |
| 31 | Live defense guide | PDF §Defense | `docs/DEFENSE.md` | Doc | ✅ Done |
| 32 | README (fresh machine → running ≤15min) | PDF §README | `README.md` | README | ✅ Done |
| 33 | MEASURANDS.md | plan.md §6.4 | `docs/MEASURANDS.md` | Doc | ✅ Done |
| 34 | DISCLOSURES.md | PDF §Disclosure | `docs/DISCLOSURES.md` | Doc | ✅ Done |
| 35 | DECISIONS.md | plan.md §16 | `docs/DECISIONS.md` | Doc | ✅ Done |
| **Process** |
| 36 | Continuous commits from hour 0 | PDF §Process | Git history (multiple commits) | Commit log | ✅ Active |
| 37 | Deterministic (same in → same out) | PDF §Determ | Pinned seeds & sorting | `floorscan repro` | ✅ Done |
| **Hard Surfaces** |
| 38 | Mirror handling | PDF §Hard | Free-space violation filter | Code | ✅ Done |
| 39 | Glass/window handling | PDF §Hard | Confidence masking | Code | ✅ Done |
| 40 | Low-light handling | PDF §Hard | Quality gates | Code | ✅ Done |
| 41 | Textureless walls | PDF §Hard | Global plane priors | Code | ✅ Done |

**Legend:** ✅ Done / Passed | 🔄 Ready / In Progress | ⬜ TODO | 🔴 Blocked
