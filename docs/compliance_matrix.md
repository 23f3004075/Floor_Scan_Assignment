# Compliance Matrix

| # | Requirement | Source | Implementation | Artifact | Status |
|---|---|---|---|---|---|
| **Capture & Input** |
| 1 | Capture route + protocol page | PDF §Capture | `docs/capture_protocol.md` | Protocol doc | ⬜ TODO |
| 2 | Device matrix | PDF §Capture | `docs/device_matrix.md` | Matrix doc | ⬜ TODO |
| 3 | Three input tiers (photo/video/LiDAR) | PDF §Tiers | `src/floorscan/cli.py` auto-detection | CLI | ✅ Skeleton |
| 4 | One command per capture | PDF §CLI | `floorscan run <input>` | CLI | ✅ Done |
| **Output Contract** |
| 5 | Per-room walls (lengths + CI) | PDF §Output | `schema.py` → Wall, Measurement | plan.json | ✅ Schema |
| 6 | Per-room ceiling height (+ CI or not_observed) | PDF §Output | `schema.py` → Measurement / NotObserved | plan.json | ✅ Schema |
| 7 | Per-room floor area (+ CI) | PDF §Output | `schema.py` → Measurement | plan.json | ✅ Schema |
| 8 | Openings (type, width, height, CI) | PDF §Output | `schema.py` → Opening | plan.json | ✅ Schema |
| 9 | Stitched multi-room plan + adjacency | PDF §Output | `schema.py` → PropertyPlan, AdjacencyEdge | plan.json | ✅ Schema |
| 10 | Damage regions (class + extent + CI) | PDF §Output | `schema.py` → DamageRegion | plan.json | ✅ Schema |
| 11 | Concealed-damage flags + rule ID | PDF §Output | `schema.py` → ConcealedDamageFlag | plan.json | ✅ Schema |
| 12 | Scope line items keyed to surfaces | PDF §Output | `schema.py` → ScopeLineItem | plan.json | ✅ Schema |
| 13 | CI on every measurement | PDF §Output | Measurement.ci_low/ci_high everywhere | plan.json | ✅ Schema |
| 14 | JSON to published schema | PDF §Output | Pydantic export → JSON Schema | schema/ | ✅ Done |
| 15 | Rendered plan (SVG/PNG) | PDF §Output | `render/plan_svg.py` | plan.svg/png | ✅ Skeleton |
| **Gates** |
| 16 | Opening widths ≤2cm on ≥85% (LiDAR) | PDF §Gates | `geometry/openings.py` | bench/ | ⬜ TODO |
| 17 | Ceiling height ≤1.5cm | PDF §Gates | `geometry/planes.py` | bench/ | ⬜ TODO |
| 18 | Repeatability ≤1cm or 0.5% per wall | PDF §Gates | `bench/repeatability.py` | bench/ | ⬜ TODO |
| 19 | Video tier ±3% | PDF §Gates | `_run_video()` | bench/ | ⬜ TODO |
| 20 | Photo tier ±8% wall + footprint | PDF §Gates | `_run_photo()` | bench/ | ⬜ TODO |
| **Benchmark & Evaluation** |
| 21 | Benchmark: ≥3 rooms + connector | PDF §Benchmark | Human capture | data/raw/ | ⬜ HUMAN |
| 22 | Furnished room with staged damage (2 classes) | PDF §Benchmark | Human capture | data/raw/ | ⬜ HUMAN |
| 23 | All 3 tiers on same rooms | PDF §Benchmark | Human capture | data/raw/ | ⬜ HUMAN |
| 24 | Repeat capture (≥1 room, ≥1 tier) | PDF §Benchmark | Human capture | data/raw/ | ⬜ HUMAN |
| 25 | Ground truth (laser/tape, 3 repeats) | PDF §Benchmark | Human measurement | data/ground_truth/ | ⬜ HUMAN |
| 26 | Drift ablation (ON vs OFF) | PDF §Drift | `bench/ablate_drift.py` | bench/ | ⬜ TODO |
| 27 | Head-to-head vs consumer app (2 rooms) | PDF §H2H | `bench/headtohead.py` | bench/ | ⬜ TODO |
| 28 | Calibration (coverage 80/90/95%) | PDF §Cal | `uncertainty/conformal.py` | bench/ | ⬜ TODO |
| **Fix Loop** |
| 29 | Fix declaration committed before fix | PDF §Fix | `docs/fix_declaration.md` | git tag `before` | ⬜ TODO |
| 30 | Before/after results regenerable | PDF §Fix | `make fixloop` | bench/ | ⬜ TODO |
| **Documentation** |
| 31 | Technical report ≤6 pages | PDF §Report | `docs/technical_report.pdf` | Report | ⬜ TODO |
| 32 | README (fresh machine → running ≤15min) | PDF §README | `README.md` | README | ⬜ TODO |
| 33 | MEASURANDS.md | plan.md §6.4 | `docs/MEASURANDS.md` | Doc | ✅ Done |
| 34 | DISCLOSURES.md | PDF §Disclosure | `docs/DISCLOSURES.md` | Doc | ⬜ TODO |
| 35 | DECISIONS.md | plan.md §16 | `docs/DECISIONS.md` | Doc | ⬜ TODO |
| **Process** |
| 36 | Continuous commits from hour 0 | PDF §Process | Git | Commit log | 🔄 Active |
| 37 | Deterministic (same in → same out) | PDF §Determ | Seeds, pinned deps | Tests | ⬜ TODO |
| **Hard Surfaces** |
| 38 | Mirror handling | PDF §Hard | Detection + masking | Code | ⬜ TODO |
| 39 | Glass/window handling | PDF §Hard | Confidence masking | Code | ⬜ TODO |
| 40 | Low-light handling | PDF §Hard | Quality gates | Code | ⬜ TODO |
| 41 | Textureless walls | PDF §Hard | Plane priors | Code | ⬜ TODO |

**Legend:** ✅ Done | 🔄 In Progress | ⬜ TODO | 🔴 Blocked
