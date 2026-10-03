# Plan: Phone-Captured Whole-Property Floor Plan Pipeline (Applied AI Case Study)

Deadline: **Oct 5, 2026, 7:00 PM IST** (public GitHub repo via form). Defense later: live walk-in test with tools closed.

_Updated Oct 3 after inspecting `single_room.zip` (findings in Sec 2.1; they changed Sec 4, 6.1, 6.4, 9, 15, 17)._

---

## 0. TL;DR

- **Product:** `capture (iPhone) -> one command -> stitched whole-property floor plan + per-room dimensions + damage + scope + JSON + rendered plan`, with a **calibrated confidence interval on every number**.
- **Hard part is not the LiDAR path.** It is (a) the **photo tier** (no depth, no poses, per-room folders that must stitch into one plan), (b) **honest calibration** (confident garbage on thin input caps the total score), (c) **drift accountability** with an on/off ablation, and (d) **a fix loop that actually ships**.
- **Winning shape:** one unified geometric core (gravity-aligned planes -> room polygons -> openings -> stitched plan) fed by three different "evidence front-ends", and one shared uncertainty layer calibrated per tier.
- **Capture route:** **Route 2 (stock protocol)**. Native Camera for photo/video, a free LiDAR logging app (Stray Scanner, to verify day 0) for LiDAR. No Xcode/TestFlight risk in a 48h window.
- **The provided capture already exposes three concrete traps** (Sec 2.1): the **ceiling is never observed** (camera always looks down), **vertical drift is ~4 cm in 37 s** (more than 2x the whole 1.5 cm ceiling gate), and the **pose/camera axis convention must be auto-detected**, not assumed.
- **Biggest time risks:** collecting the benchmark with ground truth, photo-tier stitching, and not leaving time for the fix loop (25% of score) and the fresh-machine README test.

---

## 1. Problem identification

### 1.1 What is being asked
Build a system that turns consumer iPhone capture into a **poly.cam / magicplan-style whole-property plan**, from **any of three input tiers** with the **same output contract**:

| Tier | Input | Hardware | Target accuracy (gate) |
|---|---|---|---|
| Photos | 2-8 stills per room, one folder per room, no depth/poses | iPhone 15+ | wall lengths +/-8%, footprint +/-8%, calibrated intervals |
| Video | handheld walkthrough clip | iPhone 15+ | +/-3% |
| LiDAR | depth + poses + intrinsics | Pro-class | opening widths <=2 cm on >=85%, ceiling <=1.5 cm, repeatability <=1 cm or 0.5% per wall |

Output per capture: per-room plan (walls, ceiling height, floor area, openings), stitched multi-room plan with correct adjacency, damage regions (class + metric extent), concealed-damage flags with the rule that fired, scope line items keyed to surfaces, CI on every measurement, JSON to the published schema, rendered plan, one command.

### 1.2 What the grader is really testing (read between the lines)
| Row | Hidden trap | Implication for design |
|---|---|---|
| Walk-in test (30%) | Unseen space, their iPhone, their laser, cold run, live | Generalisation > tuning. No per-scene hand fixes. Runtime must fit a live demo, offline. |
| Fix loop (25%) | "Analysis with no shipped fix = 0"; before/after must be regenerable | Pre-register fix declaration in git, tag `before`/`after`, one `make fixloop` command. |
| Benchmark (15%) | Claims must reproduce from raw inputs | Deterministic pipeline, seeded, cached model outputs with live fallback. |
| Compliance matrix (10%) | "Different product than specified" | Build matrix on day 0 and update continuously. |
| Head-to-head (10%) | "Benchmark avoidance" | Choose a real consumer app, same rooms, report losses honestly. Need to tie/beat on >=70% of dims. |
| Capture route (5%) | Non-engineer experience | Protocol is followed *literally*. Ambiguity = bad capture. Write it like a recipe. |
| Process evidence (5%) | Single-commit repos score 0 | Commit continuously from hour 0. |

### 1.3 Traps to design around explicitly
1. **Photo tier cannot be "single rooms only"** - it auto-fails the stitch row. Adjacency must be inferred from per-room folders.
2. **Ceiling height: repeatable-but-biased vs unrepeatable** - the report must say which one you have. So compute *both* spread across captures and bias vs laser.
3. **"Poses used as-is" fails drift** - need an explicit correction + ablation figure.
4. **Detection is scored with widths** - phantom and missed openings both count as misses.
5. **Calibration is scored at every tier** - wide-but-honest beats narrow-but-wrong.
6. **Ground-truth definitions** - pipeline and laser must measure the *same thing* (clear interior wall-to-wall distance, away from baseboards). Define this once, document it, use it everywhere.
7. **Mirrors, glass, wet-look surfaces, low light** are explicitly demanded in the submission.

### 1.4 Honest feasibility note
- **<=2 cm on >=85% of openings** from iPhone LiDAR depth (low native resolution) is aggressive. Plan to hit it with RGB-edge + wall-plane ray intersection (Sec 6.1), but report the real number.
- **Photo tier +/-8%** is realistic only with metric-depth priors and a scale anchor (Sec 6.3).
- Do not over-claim. A failing gate with a correct root cause and shipped fix is worth more than a hidden failure.

---

## 2. Things to resolve in the first hour (and email questions)

Reply to the email with short questions (they invite it), but do **not** block on answers:
1. Where is the **"published schema"** / Round 1 contract? (The PDF references it but doesn't include it.) Check whether the **Sample Data** folder in the email shows the expected format.
2. Does the **48h deadline** apply to the full scope (benchmark + head-to-head + fix loop), or is a scoped submission acceptable?
3. Is a single public repo with data pulled by script/volume acceptable for large raw data?

Unknowns about *your* setup that change the plan:
- Do you have **an iPhone** (model?) and ideally a **LiDAR Pro** device? If not, borrow one today. This is the critical path.
- Do you have a **laser distance meter + tape**? Buy/borrow today.
- Laptop: **GPU / Apple Silicon / CPU-only?** The live defense runs on *your* machine. Model choices depend on this.
- Mac available? (Only needed if you went Route 1. Plan assumes **not**.)

Not yet verified: whether `single_room.zip` is the grader's Sample Data folder, the published schema, current free-tier export limits of scanning apps, and current licenses/versions of the models named below. Check these on day 0.

### 2.1 What `single_room.zip` actually contains (inspected Oct 3)

**Layout.** One capture folder (`c00a170fe1/`, 88 MB zipped) that matches the export layout of the Stray Scanner app as far as I know it:

| File | Content (measured) |
|---|---|
| `rgb.mp4` | HEVC, **1920x1440, 60 fps, 37.2 s, 1715 frames**; stored in sensor-landscape orientation, so the picture appears rotated 90 degrees (no rotation metadata found) |
| `depth/NNNNNN.png` | **256x192**, 16-bit PNG, millimetres; 1715 files (one per RGB frame) |
| `confidence/NNNNNN.png` | 256x192, values 0/1/2; ~94% of pixels are 2 (high), ~4% mid, ~2% low |
| `odometry.csv` | per frame: timestamp, x y z, quaternion, **per-frame fx fy cx cy** (fx ~1597.9, slightly different from `camera_matrix.csv` 1599.7) |
| `camera_matrix.csv` | single 3x3 K for the 1920x1440 frame |
| `imu.csv` | ~100 Hz accel + gyro (3690 rows) |

**No ground truth is included** (no laser/tape numbers), so I could not score accuracy; what follows is a diagnostic probe on one capture (back-projected depth with the odometry poses), not a benchmark. Scene: a small furnished space with a toilet/tiled area, wardrobe/cupboards, sofa, fridge and a black TV screen; the last stretch of video is a close, near-blank white wall.

**Findings, and what each changes in the plan:**

| # | Finding | Evidence | Consequence |
|---|---|---|---|
| 1 | **Ceiling is never observed.** | Camera pitch is **21-42 deg looking down** (5th-95th pct, median 31 deg). Highest returns are ~2.1 m above the floor; only 0.17% of 19.7 M points are above 1.9 m; no plane peak above the furniture tops. | Pipeline must **abstain**: report ceiling height as *not observed* with a wide prior-based interval (or flag), never a confident number. This is a built-in "confident garbage" test. Protocol must force an upward sweep (Sec 4). |
| 2 | **Vertical drift ~4 cm in 37 s.** | Floor-plane height per 300-frame chunk goes -1.455, -1.465, -1.465, -1.475, -1.475, -1.495 m (1 cm bins, monotonic). | The ceiling gate is **1.5 cm**; unanchored poses can blow it by themselves. Express floor and ceiling in the **same short pose window** and re-anchor the floor plane per window (Sec 6.4). Direct evidence for the drift ablation too. |
| 3 | **Axis convention has to be detected.** | Treating `odometry.csv` rotation as camera-to-world with OpenCV-style camera axes (x right, y down, z forward) and a y-up world gives a very sharp floor peak (~1.13 M points in a single 1 cm bin, 5.7%); the ARKit-style y-up camera axes gave a far smeared one (~139 k per bin). | Ingest tries both and keeps the one with the sharper gravity-plane peak; log which was chosen. Inferred from one capture, so do not hard-code it. |
| 4 | **World axes are not wall-aligned.** | Dominant horizontal direction found at ~23 deg from the world axes; several candidate wall positions per axis (furniture, cabinet faces, tiled partition), so a naive histogram does not yield a clean rectangle. | Estimate a global Manhattan yaw, then RANSAC planes with semantic/occlusion filtering; do not read walls off histograms. |
| 5 | **Depth is low-res but plentiful.** | 256x192 at 60 fps; 1715 frames. A stride of 4-6 frames already gives ~20 M points. | Subsample frames (sharpness + parallax), use confidence == 2 only; opening widths must lean on RGB edges + plane rays (Sec 6.1). |
| 6 | **Hard surfaces appear in the sample.** | Black TV screen, glossy tiles, a near-blank white wall at the end, a few very close frames (9 of 86 sampled frames have >50% of pixels under 0.8 m). | Use this capture as a regression test for glass/specular masking and close-range frame rejection. |
| 7 | **Camera height / pace.** | Phone ~1.5 m above floor; 14.5 m path in 37 s (~0.4 m/s); horizontal extent 3.6 x 4.8 m. | Protocol pace of ~0.5 m/s is realistic; keep it. |

This one capture also lets you **derive the video tier** (`rgb.mp4` alone) and **photo tier** (sample 2-8 frames) for development and calibration. State clearly in the report that derived tiers are not the reported benchmark (real native-camera captures are).

---

## 3. Strategy and priorities (48h reality)

Priority order (weights and failure caps drive this):
1. **P0 - Skeleton end-to-end** (schema, CLI, render, LiDAR tier on one room). Commit early.
2. **P0 - Benchmark capture with ground truth** (do in first ~6h, daylight; add one low-light room).
3. **P0 - LiDAR tier complete** with drift ablation + repeatability.
4. **P0 - Photo-tier whole-property stitch** (explicit fail otherwise).
5. **P1 - Video tier.** Shares most machinery with photo tier (SfM/feed-forward reconstruction + metric scale).
6. **P1 - Fix loop** (pick worst gate after first honest benchmark; ship; regen).
7. **P1 - Head-to-head** on 2 rooms.
8. **P2 - Damage + concealed rules + scope** (minimal but working, keyed to surfaces; not in the gate table).
9. **P2 - Report (<=6 pages), compliance matrix, README** - write continuously; finish in last 4h.

**Cut list if behind (in order):** polish of damage classes -> video tier refinements -> head-to-head to exactly 2 rooms / minimum dims -> fancy rendering. **Never cut:** photo stitch, drift ablation, calibration, fix loop, fresh-machine test.

---

## 4. Capture route decision

**Choose Route 2 (stock protocol).**

Why: no Apple Developer account / TestFlight review / Xcode dependency in 48h; the grader follows the page literally so a clear page is easy to optimise; free apps already expose what we need.

| Tier | Tool | Notes |
|---|---|---|
| Photo | Native Camera app | HEIC/JPEG; EXIF gives focal length (intrinsics prior). Folder per room, AirDrop/Files. |
| Video | Native Camera, 4K 30 fps, wide (1x) lens, **lock exposure/focus if possible**, no digital zoom | Intrinsics prior from metadata. |
| LiDAR | **Stray Scanner** (free iOS app that logs RGB, depth, confidence, camera matrix, odometry, IMU) - *the uploaded `single_room.zip` matches its export layout (Sec 2.1); still verify install and export on your own device* | Fallback: another LiDAR logging app that exports raw depth + poses. If only meshes export, use the mesh ingest path (Sec 6.1b). |

**Protocol page (docs/capture_protocol.md) must specify, per tier:**
- Install steps (time-boxed < 5 min), settings screenshots.
- Walk path: start at the connector/door, keep phone ~chest height, hold portrait/landscape consistently, slow pace (~0.5 m/s), overlap, loop back to start (loop closure!), pass each doorway slowly and look *through* it.
- Duration per room (e.g., 60-90 s) and per property.
- What to avoid: fast pans, covering lens, pointing only at blank white walls, mirrors/windows in frame as the main subject, moving people/pets.
- **Vertical coverage (new, from the sample capture):** at the start and the end of each room, do a slow **tilt sweep**: look at the floor, then up the wall to the **ceiling line**, then back, in one continuous motion of ~5 s, standing still. Hold the phone upright, not tilted down. Without this the ceiling is never seen and ceiling height cannot be measured. Also: do not finish the walk with the camera inches from a blank wall.
- **Photo-tier folder rules:** folders named `01_<room>`, `02_<room>` in **walk order**; photo 1 = standing in the doorway looking in; photo 2 = diagonal corner shot showing ceiling + floor edges; remaining photos cover the other corners; **last photo = looking back through the door you came in**. (This gives the doorway/adjacency cues the stitcher needs.)
- **Optional scale cue** (e.g., an A4 sheet or credit card on the floor in one photo per room) if it can be done unambiguously. Pipeline must still work (with wider CI) when absent.
- Handoff: one folder, AirDrop/USB, then `floorscan run <folder>`.

Device matrix (hypotheses to be replaced by measured numbers):

| Tier | Runs on | Honest expected accuracy |
|---|---|---|
| LiDAR | iPhone/iPad Pro with LiDAR | to be measured; target walls ~1-2 cm, ceiling ~1 cm |
| Video | any iPhone 15+ (LiDAR phones use RGB only) | target +/-3% walls |
| Photo | any iPhone 15+ | target +/-8% walls/footprint |

### 4.1 Input modes: live LiDAR, live phone video, video upload (added Oct 3)

Three user-facing modes feed the **same** core through a `FrameSource` abstraction (batch = replay of a live stream):

| Mode | Tier | Source | Notes |
|---|---|---|---|
| A. Live LiDAR | LiDAR | Record3D-style streaming (verify free Python API and limits), or a small custom ARKit streamer (Route 1, only if time allows) | Guaranteed fallback: record on device with Stray Scanner, transfer folder, run as batch |
| B. Live phone video | Video | Mobile web page (`getUserMedia`) streaming to a local HTTPS server; also records full-quality video locally | iOS Safari needs HTTPS; self-signed cert or tunnel must work offline; verify on the real device |
| C. Video upload | Video | Native Camera clip (`.mov`/`.mp4`, rotation + focal-length metadata) | Simplest; most likely to be used at the walk-in test |

Rules: live = **guidance + provisional plan** (periodic re-solve), final numbers come from a deterministic final solve on the best available data (prefer full-quality recording over the compressed live stream, and report which). Live guidance signals: floor seen, **ceiling seen**, wall coverage, parallax, loop closed, too fast / too close / low light, mirror/glass. Priority: batch pipeline first, live modes as thin wrappers; minimum viable live = replay-from-folder "simulated live" CLI so the path is tested. Full agent instructions: `agent_prompt.md`.

---

## 5. Architecture

```
            +-------------------+     +------------------+     +-------------------+
Photos ---> | Photo front-end   |     | Video front-end  |     | LiDAR front-end   |
(folders)   | feed-fwd recon +  |     | SfM/SLAM + metric|     | depth+pose+K      |
            | metric depth+scale|     | depth + scale    |     | fusion / mesh     |
            +---------+---------+     +--------+---------+     +---------+---------+
                      \                        |                        /
                       v                       v                       v
                 +---------------------------------------------------------+
                 | Unified Scene Evidence (gravity-aligned, metric, w/ sigma)|
                 | frames, poses, points/depth, semantics, per-source sigma |
                 +----------------------------+----------------------------+
                                              v
                 +---------------------------------------------------------+
                 | Geometry core                                           |
                 | planes (floor/ceiling/walls) -> Manhattan regularise    |
                 | -> room polygon -> openings (RGB edges x plane rays)   |
                 +----------------------------+----------------------------+
                                              v
                 +---------------------------------------------------------+
                 | Stitcher: room segmentation / adjacency graph / pose    |
                 | graph + plane anchors (drift) / non-overlap constraints |
                 +----------------------------+----------------------------+
                                              v
        +-----------------+   +------------------------+   +-------------------+
        | Damage + rules  |   | Uncertainty/calibration|   | Scope line items  |
        | masks->surface  |   | per-tier conformal     |   | keyed to surfaces |
        +--------+--------+   +-----------+------------+   +---------+---------+
                 \                        |                          /
                  v                       v                         v
                       JSON (pydantic -> JSON Schema) + SVG/PNG plan
```

Key principle: **tiers differ only in front-end and in the sigma they hand to the shared core.** This is what makes "same output contract" credible, and it makes the defense story simple.

---

## 6. Tier pipelines

### 6.1 LiDAR tier (the anchor tier)

**a) Raw depth path (preferred)**
1. Ingest (`io/stray_scanner.py`; accept the zip or the folder, including one nested capture folder): RGB frames (landscape, rotate for display/models, intrinsics refer to the **unrotated** frame), depth (256x192, uint16 mm -> metres), confidence (keep == 2), **per-frame intrinsics from `odometry.csv`** (fall back to `camera_matrix.csv`, scaling K by 256/1920 for depth), poses, IMU. Depth and RGB frame indices are 1:1. Drop low-confidence and out-of-range (<0.2 m, >5 m) depth; reject blurred and very-close-range frames; subsample by sharpness + parallax.
2. **Pose convention + gravity:** test both camera-axis conventions (OpenCV-style vs ARKit-style), pick the one that yields the sharpest floor-plane height peak, log the choice; confirm gravity direction against the IMU and the floor fit. Estimate global Manhattan yaw (the world is not wall-aligned).
3. Fuse into a point cloud / TSDF (Open3D) in gravity-aligned frame.
4. **Planes:** floor and ceiling via 1-D histogram of heights along gravity (robust mode, tolerant to furniture/light fixtures), then **vertical planes by RANSAC / region growing**, refined by least squares on inliers.
5. **Ceiling height** = distance between fitted floor and ceiling planes (averaged over thousands of points -> sub-cm precision; the risk is *bias* and *drift*, see 6.4). **If no ceiling plane is observed** (as in `single_room.zip`), output `ceiling_height: not_observed` with a wide prior interval and a `low_confidence` flag instead of a number.
6. **Walls:** wall length = distance between **intersection lines of adjacent wall planes** (long-baseline, robust to furniture occluding corners) instead of picking boundary points.
7. **Openings (doors/windows):** hybrid
   - candidates from gaps/discontinuities in wall-plane occupancy and depth;
   - class + precise edges from RGB: open-vocabulary detection/segmentation (door, window, opening) -> edge pixels -> **cast rays through the camera model and intersect the fitted wall plane** -> metric width independent of depth noise (1 px at ~3 m with fx ~1500 px is a few mm).
   - Multi-view fusion across frames; a candidate must be seen consistently to count (kills phantoms).
8. Room polygon from wall planes (Manhattan-regularised with an opt-out for non-orthogonal walls), floor area from polygon, minus nothing (state definition).

**b) Mesh fallback path:** if the chosen free app only exports meshes (OBJ/PLY/USDZ), run the same plane/layout code on mesh vertices/faces. Keeps tier alive if raw depth export is blocked.

### 6.2 Video tier
1. Extract keyframes (blur/sharpness filter, parallax-based selection).
2. Reconstruct poses + geometry: **SfM (COLMAP/pycolmap or GLOMAP)** *or* a feed-forward reconstructor (**VGGT / MASt3R / MapAnything** class models, check licenses and runtime on your hardware). Keep the option of using whichever is more robust on textureless indoor walls.
3. **Metric scale** (no LiDAR): ensemble of
   - metric monocular depth (e.g., **Apple Depth Pro**, Depth Anything V2/V3 metric, UniDepth, MoGe-2) aligned to SfM points,
   - known-size anchors (standard door height/width priors, credit card / A4 cue if present in protocol),
   - gravity from IMU if available (video metadata may not carry it; don't depend on it).
   Scale uncertainty = disagreement across estimators plus calibrated inflation.
4. Hand off to the same geometry core with larger sigmas. Target walls +/-3%.

### 6.3 Photo tier (explicitly the floor: "any picture in, results out")
Per room (2-8 stills, no poses):
1. Intrinsics from EXIF (focal length 35mm-equiv -> pixels). Distortion assumed small; allow estimate when overlap permits.
2. Multi-view geometry from few wide-baseline images with a feed-forward model (VGGT / MASt3R / MapAnything class) -> relative poses + pointmaps; if only 1-2 usable images, fall back to single-image metric depth + layout priors.
3. Metric scale as in 6.2; **per-room scale uncertainty must be explicit**.
4. Geometry core -> room polygon (Manhattan prior is *more* important here), openings from RGB detection with plane-ray widths.
5. **Whole-property stitch across folders (the failing row for most):**
   - Folder order = walk order (protocol-enforced) gives a prior chain.
   - **Doorway evidence:** first/last photo cues (looking in / looking back through the door) -> match door position/width/height between consecutive rooms (width and sill/head heights must agree within tolerance).
   - Cross-folder image matching (features / learned matchers) for the doorway views to confirm adjacency; assign adjacency probabilities.
   - Place rooms by **constrained optimisation**: door-to-door alignment, shared-wall coincidence (+ plausible wall thickness), **no overlap** (shapely), Manhattan yaw alignment, footprint prior.
   - Output adjacency with confidence; if ambiguous, say so and widen the footprint interval rather than guess confidently.
6. Calibrated intervals scale with: number of photos, parallax, scale-anchor availability, model disagreement.

### 6.4 Shared: drift, bias, repeatability

**Drift accountability (multi-room LiDAR/video):**
- Method: **pose graph** (GTSAM or scipy/Open3D PoseGraph) with
  - odometry edges,
  - **loop-closure edges** from revisiting the connector/start (protocol requires returning),
  - **plane-anchored constraints:** floor/ceiling height consistency, global **Manhattan yaw** snapping, shared-wall coplanarity across rooms.
- **Ablation:** render stitched footprint with correction ON vs OFF, overlay ground truth footprint, report area/perimeter/closure-gap numbers. `make ablate-drift`.

**Vertical drift (measured on the sample, ~4 cm in 37 s):**
- Fit the floor plane in sliding pose windows and re-anchor each window to a common floor height; measure ceiling height **within a window that sees both floor and ceiling** (the protocol's tilt sweep), or as the difference of two plane heights each expressed relative to the same locally-anchored poses. Never subtract a floor height from one end of the capture and a ceiling height from the other.
- Report floor-height-per-window before/after anchoring as part of the drift ablation.

**Ceiling bias vs repeatability:**
- Compute (i) spread across repeat captures (<=1 cm gate) and (ii) mean signed error vs laser per room (bias). Report which failure mode (if any) is present. Fit a *documented* per-device scale/offset correction only if it is estimated on data held out from evaluation (otherwise it is benchmark-fitting).

**Determinism ("same room in, same plan out"):**
- Fixed seeds; deterministic RANSAC (seeded or replaced with deterministic LO-RANSAC + final LS refit); canonical orientation (gravity + dominant wall direction) and canonical start corner; sorted frame ordering; pinned dependency versions; model outputs cached with hash keys.

---

## 7. Damage, concealed-damage and scope (keep minimal but real)

- **Detection:** open-vocabulary segmentation (SAM 2 / Grounded-SAM class, or a VLM for classification) over frames -> masks for classes such as *water stain, mould/discolouration, crack, peeling paint, efflorescence*. Run locally; any external API must be disclosed and must have a local fallback (walk-in test is live).
- **Metric extent:** project mask pixels onto the already-fitted surface plane (ray-plane intersection) -> area (m2) and length (m) per surface. Aggregate across views; report CI from view disagreement.
- **Concealed-damage rules:** small, auditable YAML rule table with IDs, e.g. ceiling stain near/below a wet-room footprint; staining low on walls near baseboard; bubbling paint + discolouration pairing. Each flag records `rule_id`, inputs, and fired condition.
- **Scope line items:** table mapping (surface type, damage class, extent) -> line item (e.g., drywall repair, repaint, ceiling patch) with quantity from metric extent and a unit; keyed by `surface_id`.
- Benchmark requirement: one furnished room with staged damage in **two classes**. Stage safe, realistic proxies (e.g., printed/painted stains, tape-marked cracks) with known measured extent.

---

## 8. Uncertainty and calibration

**Layered intervals:**
1. **Propagated geometric uncertainty:** plane-fit covariance, bootstrap over frames/points, pose uncertainty from pose graph, scale uncertainty from estimator disagreement.
2. **Empirical calibration:** split-conformal (or normalised-residual quantile) per tier and per measurement type so nominal 90% intervals achieve ~90% empirical coverage.
3. **Abstention / widening:** quality gates (low parallax, few photos, blur, low light, mirror/glass detected, textureless, low depth confidence) multiply sigma or flag `low_confidence` instead of emitting a tight confident number.

**Data for calibration (allowed with disclosure):**
- Your own benchmark (too small alone; use leave-one-room-out).
- Public data with ground truth, e.g. **ARKitScenes** (iPad LiDAR depth/poses/intrinsics + layout annotations) and **ScanNet++** (iPhone video + laser scans; access form required, may be too slow for 48h), plus synthetic degradation of LiDAR captures into video/photo-like inputs *for development and calibration only* (state clearly this is not the reported benchmark).
- Check dataset licenses and disclose usage.

**Reporting:** coverage at 80/90/95% per tier, reliability plot, mean interval width, and a table of "confident-garbage" checks on deliberately bad inputs (e.g., 1 photo, dark room, mirror-heavy room) showing the system widens/abstains.

---

## 9. Hard surfaces and failure modes (must be covered in submission)

| Condition | Effect | Handling |
|---|---|---|
| **Mirrors** | LiDAR/SfM sees a "virtual room" behind the wall | Detect with segmentation prompts + free-space/visibility consistency (points behind an established opaque plane are rejected); exclude from plane fits |
| **Glass / windows** | Depth passes through or returns noise | Mask as `glass`; use frame edges + RGB for opening geometry, not depth |
| **Wet-look / specular floors, glossy tiles, black screens (TV)** | Depth outliers, SfM false matches; both appear in `single_room.zip` | Confidence masking, robust fitting, widen CI; keep the sample as a regression test |
| **Low light** | RGB tiers degrade; LiDAR unaffected | Blur/exposure gates; tier-specific CI inflation; document LiDAR as the low-light tier |
| **Textureless white walls** | SfM/pose failure | Prefer feed-forward model + plane priors; widen CI |
| **Clutter/furniture** | Hidden corners, floor fits contaminated; several wall-like planes per axis (seen in the sample) | Plane-intersection corners; robust histograms; semantic filtering of furniture/cabinet faces |
| **Ceiling never in view** | No ceiling plane at all (seen in the sample) | Abstain with a wide interval; protocol tilt sweep |
| **Non-Manhattan rooms** | Regularisation errors | Opt-out flag when residuals exceed threshold |
| **Large open spaces (>5 m)** | LiDAR range limit | Flag and widen CI |

Include at least one benchmark room or capture with a hard surface (mirror/glass/low-light) and report results.

---

## 10. Benchmark design

Composition (as specified, cannot be flattered):
1. **Multi-room set:** >=3 rooms + a connector (hallway/door), continuous capture with a closing loop.
2. **Furnished room with staged damage** in two classes.
3. **All three tiers on the same rooms**, including the multi-room set (photo tier = per-room folders that must stitch).
4. **Repeat capture:** at least one room captured twice at the same tier (ideally at **every** tier, at different times).
5. **Ground truth for everything:** laser/tape.

**Ground-truth protocol (write it down; it is part of the reproducibility bundle):**
- Define measurands: *clear interior wall-to-wall distance at ~1.2 m height (above baseboard), ceiling height at >=3 points (median), door/window clear opening width and height, floor area from the measured polygon (diagonals checked).*
- Take **3 repeats per measurement**, record the spread (ground truth has its own error: state it).
- Sketch with measurement labels, photograph the laser readings, save in `data/ground_truth/*.json` (+ photos).
- Record device model, app and version, lighting, time.
- Save raw sensor data (Stray Scanner folders, video files, photos) untouched.

**Gates computed by `floorscan bench`:** per-tier tables for opening widths (detection precision/recall + widths), ceiling height (error + spread + bias), repeatability (per wall), drift ablation, photo-tier stitch (adjacency correct, overlap-free, footprint error), wall length by tier, calibration coverage, runtime.

---

## 11. Head-to-head (Part 3)

- Pick **one** consumer app and record **name + version** (candidates: magicplan, Polycam, Canvas/RoomPlan-based apps, Scaniverse). Choose one whose **free tier exports usable dimensions/geometry**; confirm on day 0.
- Use **2 benchmark rooms** at the LiDAR tier. Shared dimensions: wall lengths, ceiling height, floor area, opening widths/count.
- Measure the app's own reported/exported dimensions (don't re-extract them with your own code, which would be unfair).
- One table: laser GT | ours | ours error | app | app error | winner. Need to **beat or tie on >=70%** of shared dims. Report honest losses.

---

## 12. Fix loop plan (25% of score)

1. Run the full benchmark honestly -> `bench/results_before.json` (git tag `before`).
2. Identify the **single worst gate** (failing number).
3. Write `docs/fix_declaration.md` (one page) **and commit it before coding the fix:** failing number, root-cause hypothesis + evidence (plots/diagnostics), the fix, predicted number after.
4. Ship the fix; run again -> `bench/results_after.json` (tag `after`).
5. `make fixloop` regenerates both runs and prints a diff table; include a readable code diff.
6. If prediction misses: write an honest post-mortem.

Likely candidates (decide from data, not now): opening widths <=2 cm, ceiling bias, photo-tier stitch adjacency, drift. Don't sandbag v0; the honest first benchmark will reveal real failures.

---

## 13. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | **Python 3.11** | ecosystem for geometry + CV + ML |
| Env | **uv** (or poetry) + **Docker** image + pinned lockfile | clean-machine 15-min README |
| CLI | **Typer**, `floorscan run <capture_dir> --out out/` with **tier auto-detection** (folders of images / video file / LiDAR export) | "one command per capture" |
| Schema | **Pydantic v2** -> exported JSON Schema; validate every output | schema compliance |
| Numerics | numpy, scipy, scikit-learn | plane fits, optimisation, calibration |
| Geometry | **Open3D**, trimesh, **shapely** (overlap, polygons), networkx (adjacency graph) | planes/TSDF/mesh, polygon ops |
| Pose graph | **GTSAM** (or scipy least-squares / Open3D PoseGraph as lighter fallback) | loop closure + constraints |
| SfM / recon | **pycolmap / GLOMAP**; feed-forward: **VGGT / MASt3R / MapAnything** (check license, speed on your hardware) | robust few-view and video |
| Metric depth | **Depth Pro**, Depth Anything V2/V3 metric, UniDepth/MoGe-2 (ensemble) | scale for RGB-only tiers |
| Matching | LightGlue / MASt3R matching | cross-folder doorway matching |
| Segmentation / detection | **SAM 2** + open-vocab detector (Grounding DINO / YOLO-World / Florence-2) | doors, windows, mirrors, glass, damage |
| Damage classification | local VLM (e.g., Qwen2.5-VL class) or CLIP-style zero-shot | runs offline; any API use disclosed + fallback |
| Video I/O | ffmpeg, OpenCV, pillow-heif, exifread | frames, HEIC, EXIF |
| Render | matplotlib/SVG (+ PNG export) | clean dimensioned plan, intervals shown |
| Reproducibility | Makefile/just, seeded runs, cached model outputs keyed by hash, `scripts/fetch_weights.sh` | grader regenerates numbers |
| Tests | pytest on geometry primitives with synthetic rooms (known answers) | catches regressions, supports process evidence |

**Compute rule:** every model must run on the *demo laptop* within a live-demo budget (target: a room in a few minutes, a property in < ~10 min on the real machine; measure and report timing). Cache for the benchmark, but the **live path must work cold and offline**.

**Disclosure list:** models, datasets, and any APIs go in `docs/DISCLOSURES.md` with licenses (some research models are non-commercial; fine for an assessment but disclose).

---

## 14. Repo layout

```
floorscan/
  README.md                  # fresh machine -> running in <15 min, one command per capture
  Makefile                   # setup, run, bench, ablate-drift, fixloop, repro
  pyproject.toml / uv.lock
  Dockerfile
  scripts/fetch_weights.sh
  src/floorscan/
    cli.py  schema.py
    io/        stray_scanner.py video.py photos.py mesh.py
    geometry/  gravity.py planes.py layout.py openings.py stitch.py pose_graph.py
    perception/ depth_models.py recon.py segmentation.py damage.py
    uncertainty/ propagate.py conformal.py quality_gates.py
    scope/     rules.yaml concealed.py line_items.py
    render/    plan_svg.py
    bench/     gates.py repeatability.py headtohead.py ablate_drift.py runtime.py
  data/        raw/  ground_truth/  app_exports/   # large files by script/volume
  docs/
    compliance_matrix.md  capture_protocol.md  device_matrix.md
    fix_declaration.md  DISCLOSURES.md  DECISIONS.md  technical_report.pdf
  tests/
```

### Compliance matrix (skeleton: requirement -> path -> artifact -> status)
Maintain `docs/compliance_matrix.md` from hour 0. Rows to include at minimum: capture route + device matrix; repo/README/one command; reproduction bundle; benchmark report (3 tiers, repeatability, head-to-head, timing); fix loop bundle; technical report (<=6 pp); raw benchmark data; each output-contract item (walls, ceiling, area, openings, stitched plan, damage regions, concealed flags + rule, scope items, CI everywhere, JSON schema, rendered plan); each gate row; hard-surface coverage.

### Technical report (<=6 pages) outline
1) Architecture 2) Tier design + device matrix 3) Drift handling + ablation 4) Error budget 5) Calibration analysis 6) Fix-loop story 7) Known failure modes. Dense, figures over prose.

---

## 15. Schedule (~48h, adjust to the real clock)

| Block | Work | Output |
|---|---|---|
| **H0-3** | Email questions; inspect sample data + schema; install capture apps; write the `stray_scanner.py` ingest and get `single_room.zip` through it end-to-end (floor plane, convention detection, ceiling-not-observed path); environment/uv/Docker; repo skeleton, schema, CLI stub; compliance matrix v0; **first commits** | repo live, apps verified |
| **H3-9** | **Capture benchmark** (daylight; multi-room + staged-damage room + repeat; all three tiers; plus one low-light/mirror/glass capture) + ground truth (3 repeats) | `data/raw`, `data/ground_truth` |
| **H9-20** | LiDAR tier: ingest -> planes -> room polygon -> ceiling/walls -> openings -> render -> JSON; synthetic-room unit tests; repeatability; pose graph + drift ablation | LiDAR gates computed |
| **H20-32** | Photo tier (per-room recon, scale, **cross-folder stitch**); video tier on same machinery; quality gates | photo + video gates computed |
| **H32-38** | Calibration (conformal, coverage tables); damage/scope minimal; head-to-head 2 rooms | calibration + H2H tables |
| **H38-44** | Full benchmark run -> pick worst gate -> **fix declaration commit** -> ship fix -> before/after bundle | fix-loop bundle |
| **H44-48** | Technical report, README, protocol, device matrix, compliance matrix; **fresh-machine test** (clean Docker/VM, time it); cold-run rehearsal with a friend following the protocol; submit with buffer | submission |

Do captures and ground truth **first**: everything downstream depends on them, and the fix loop needs time after the first honest benchmark.

---

## 16. Process evidence and defense prep

- **Commit continuously** (small, meaningful commits from hour 0: skeleton, schema, each module, each benchmark run, fix declaration before fix). No giant final dump.
- Keep `docs/DECISIONS.md` as you go: for each design decision, write *alternatives considered, why chosen, what would change it*. The defense is live with tools closed, so be able to explain, from memory: plane fitting + RANSAC, why wall length via plane intersection, ray-plane intersection for openings, pose graph + plane anchors, conformal calibration, photo-tier adjacency logic, the error budget, and the fix-loop root cause.
- Rehearse: sketch the pipeline on paper; derive the ray-plane width formula; state what each gate number means and its ground-truth error.

---

## 17. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| No LiDAR iPhone / laser meter available | medium | Borrow today; fallback = public data (ARKitScenes) for development, but the benchmark must be self-captured, so flag early |
| Capture app can't export raw depth | medium | Mesh fallback path; alternate app; verify in H0-3 |
| Photo-tier stitch unreliable | high | Protocol-driven doorway shots + folder order priors; output adjacency confidence; widen footprint CI |
| Models too slow/heavy on demo laptop | medium | Pick lighter models, cache for benchmark, keep live path small, measure timing early |
| Schema unknown | medium | Ask; use sample data; design with pydantic so it's quick to adapt |
| Vertical drift (~4 cm in 37 s on the sample) breaks the 1.5 cm ceiling gate | high | Windowed floor re-anchoring; ceiling measured in the same window as the floor; protocol tilt sweep |
| Capture without ceiling coverage on walk-in day | medium | Abstain honestly; protocol tilt sweep; rehearse the protocol with a non-engineer |
| Opening widths miss the 2 cm gate | high | Plane-ray RGB edge method; report honestly; candidate fix-loop target |
| Time overrun | high | Cut list in Sec 3; protect fix loop, drift ablation, calibration |
| Over-claiming | medium | Calibrated intervals, abstention, honest "known failure modes" section |
