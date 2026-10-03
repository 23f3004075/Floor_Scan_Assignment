# RECON: Project Understanding

## 1. Applied_AI_Case_Study.pdf (spec)
Build a system converting iPhone captures (3 tiers: photos, video, LiDAR) into dimensioned whole-property floor plans with calibrated CIs. Gates: opening widths ≤2cm on ≥85% (LiDAR), ceiling ≤1.5cm, repeatability ≤1cm/0.5%, video ±3%, photo ±8%. Scoring: walk-in 30%, fix loop 25%, benchmark 15%, compliance 10%, head-to-head 10%, capture route 5%, process 5%. Output: JSON schema + rendered plan per capture. One command. Fresh-machine ≤15min.

## 2. plan.md (strategy)
Unified architecture: three front-ends feeding one geometry core via FrameSource. Route 2 (stock protocol, no Xcode). Priority: skeleton → benchmark capture → LiDAR → photo stitch → video → fix loop. Key findings from sample: ceiling never observed, 4cm vertical drift in 37s, OpenCV convention detected, world axes ~23° off Manhattan, depth 256×192 at 60fps. Cut list: damage polish → video refinements → head-to-head reduction.

## 3. single_room.zip (sample capture)
Stray Scanner export: `c00a170fe1/` with rgb.mp4 (1920×1440, HEVC, 60fps, 37.2s), 1715 depth frames (256×192, uint16 mm), confidence maps (94% high), odometry.csv with per-frame intrinsics, camera_matrix.csv, imu.csv. No ground truth included. Contains: toilet/tiles, wardrobe, sofa, fridge, black TV, blank white wall.

### Additional data (not in plan.md):
- `single_scan_floor_only.zip` (277MB, capture `1a8384c3f6/`, ~5250 frames per modality)
- `single_scan_with_ceiling.zip` (509MB, capture `c7d28f72c6/`, ~9747 frames per modality)

## Conflicts: plan.md vs PDF
- None identified yet (plan appears aligned with PDF requirements).
- Published schema referenced but not provided - using provisional Pydantic schema.
