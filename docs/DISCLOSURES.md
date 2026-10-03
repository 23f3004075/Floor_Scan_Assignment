# Disclosures Ledger (DISCLOSURES.md)

All third-party libraries, pretrained weights, datasets, and runtime dependencies used in `floorscan` are listed below with version, source, license, and offline capability status.

---

## 1. Third-Party Libraries & Runtimes

| Component | Version | License | Primary Purpose | Offline Verified |
|---|---|---|---|---|
| **Python** | 3.10.x | PSF License | Runtime environment | Yes (local) |
| **NumPy** | >= 1.24.0 | BSD-3-Clause | Vectorized linear algebra & point clouds | Yes |
| **SciPy** | >= 1.10.0 | BSD-3-Clause | KD-trees, optimization, robust statistics | Yes |
| **Scikit-learn**| >= 1.3.0 | BSD-3-Clause | RANSAC regressors, clustering | Yes |
| **Open3D** | >= 0.17.0 | MIT | 3D point cloud filtering, normal estimation, ICP | Yes |
| **Shapely** | >= 2.0.0 | BSD-3-Clause | 2D Polygon operations, footprint union, intersection | Yes |
| **Trimesh** | >= 3.20.0 | MIT | Geometric ray casting, plane intersections | Yes |
| **NetworkX** | >= 3.0.0 | BSD-3-Clause | Multi-room adjacency graphs, topological validation | Yes |
| **OpenCV** | >= 4.8.0 | Apache 2.0 | Image processing, feature matching, canny edge detection | Yes |
| **Pillow / pillow-heif** | >= 10.0 | HPND / LGPL | Image decoding, HEIC container support | Yes |
| **PyAV (av)** | >= 10.0 | BSD-2-Clause / LGPL | Video stream decoding (HEVC / H.264) | Yes |
| **Pydantic** | >= 2.0.0 | MIT | Schema validation, JSON schema serialization | Yes |
| **Typer / Rich** | >= 0.9.0 | MIT | CLI interface, terminal reporting | Yes |
| **svgwrite** | >= 1.4.0 | MIT | Deterministic vector SVG floor plan rendering | Yes |
| **PyTorch** | >= 2.0.0 | BSD-style | Local tensor computation (for vision backbones) | Yes |

---

## 2. Pretrained Models & Weights

To adhere strictly to the offline constraint, all model weights are cached locally and must never require live network access during evaluation or the cold walk-in demo.

| Model / Checkpoint | Version / Commit | License | Role in Pipeline | Local Storage Path |
|---|---|---|---|---|
| **MobileNetV2 / ResNet50 (torchvision)** | Default pre-trained | BSD-3-Clause | Feature backbone for damage classification | `~/.cache/torch/hub/checkpoints/` |
| **Open-Vocabulary Segmenter (FastSAM / MobileSAM / CLIP)** | Pre-downloaded weights | MIT / Apache 2.0 | Wall opening edge refinement, damage mask segmentation | `models/` |
| **Monocular Metric Depth (Depth-Anything-V2 Small)** *(Video/Photo fallback)* | v2-small | Apache 2.0 | Metric scale initialization for RGB video frames | `models/depth_anything_v2_vits.pth` |

*Note: In LiDAR mode, pure geometric RANSAC and plane-fitting methods do not require neural network weights, ensuring 100% offline, zero-dependency execution.*

---

## 3. Data Sources & Captures

| Dataset / Capture ID | Source / Hardware | Description | Ground Truth Status |
|---|---|---|---|
| `single_room.zip` (`c00a170fe1`) | iPhone LiDAR capture via Stray Scanner | 37.2s RGB-D-odometry capture of a living room | **No ground truth.** Used exclusively for ingestion, convention detection, drift analysis, and abstention testing. |
| `single_scan_floor_only.zip` | iPhone LiDAR capture | Capture without ceiling sweep | Ingestion & abstention verification |
| `single_scan_with_ceiling.zip`| iPhone LiDAR capture | Capture with complete upward ceiling sweep | Ceiling height validation |
| `tests/synth/` | Synthetically generated | Rectangular and L-shaped rooms with known geometry, openings, and noise models | Exact analytical ground truth for regression & calibration testing |

---

## 4. Regional and Contextual Priors

- **Doorway heights:** 2.0 m – 2.1 m nominal standard prior (disclosed: standard Indian and international residential door opening heights).
- **Ceiling heights:** 2.4 m – 3.0 m nominal prior (used strictly when ceiling is unobserved; flagged as unobserved).
- **Scale cue:** Standard A4 sheet (297 mm x 210 mm) or credit card (85.6 mm x 53.98 mm) optionally supported as metric scale verification in photo/video tiers.
