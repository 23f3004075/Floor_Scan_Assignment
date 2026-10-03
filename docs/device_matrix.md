# Hardware & Device Capability Matrix

Comprehensive support and performance profiling across iPhone generations, input tiers, and sensor configurations for `floorscan`.

---

## 1. Supported Devices Matrix

| Device Model | LiDAR Scanner | ARKit 6 DoF Odometry | Max Video Capture | Supported Tiers | Target Gate Accuracy |
|---|---|---|---|---|---|
| **iPhone 16 Pro / Pro Max** | Yes (dToF 5m) | Yes (A18 Pro) | 4K 120fps HDR | LiDAR, Video, Photo | Walls: ≤ 1.0 cm, Openings: ≤ 2.0 cm |
| **iPhone 15 Pro / Pro Max** | Yes (dToF 5m) | Yes (A17 Pro) | 4K 60fps ProRes | LiDAR, Video, Photo | Walls: ≤ 1.0 cm, Openings: ≤ 2.0 cm |
| **iPhone 14 Pro / Pro Max** | Yes (dToF 5m) | Yes (A16 Bionic) | 4K 60fps | LiDAR, Video, Photo | Walls: ≤ 1.0 cm, Openings: ≤ 2.0 cm |
| **iPhone 13 Pro / Pro Max** | Yes (dToF 5m) | Yes (A15 Bionic) | 4K 60fps | LiDAR, Video, Photo | Walls: ≤ 1.5 cm, Openings: ≤ 2.5 cm |
| **iPhone 12 Pro / Pro Max** | Yes (dToF 5m) | Yes (A14 Bionic) | 4K 60fps | LiDAR, Video, Photo | Walls: ≤ 1.5 cm, Openings: ≤ 2.5 cm |
| **iPad Pro 11" / 12.9" (2020+)**| Yes (dToF 5m) | Yes (M1/M2/M4) | 4K 60fps | LiDAR, Video, Photo | Walls: ≤ 1.0 cm, Openings: ≤ 2.0 cm |
| **iPhone 15 / 15 Plus** | No | Yes (ARKit Monocular) | 4K 60fps | Video, Photo | Video: ± 3% scale, Photo: ± 8% |
| **iPhone 14 / 13 / 12 (Base)** | No | Yes (ARKit Monocular) | 4K 60fps | Video, Photo | Video: ± 3% scale, Photo: ± 8% |
| **Non-Apple / Android Stills**| No | No | 1080p / 4K | Photo (SfM) | Photo: ± 8% wall & footprint |

---

## 2. Sensor Characteristics & Noise Envelope

| Sensor Component | Physical Property | Noise / Uncertainty Model | Mitigation in Pipeline |
|---|---|---|---|
| **Apple dToF LiDAR** | 256x192 mesh depth | σ ≈ 0.5 cm @ 1m; σ ≈ 2.0 cm @ 4.5m; range limit 5.0m | Confidence masking (require confidence==2), range cutoff > 4.5m |
| **Wide Camera (24mm/26mm)**| CMOS rolling shutter | Pixel noise < 1px; lens distortion k1, k2 | Per-frame focal length scaling, OpenCV undistortion |
| **ARKit Visual-Inertial Odometry** | 6-DoF pose graph @ 60Hz | Drift: ~1–4 cm vertical drift over 30s; yaw drift ~0.5°/min | Manhattan frame alignment, windowed floor re-anchoring, loop closure |
| **Apple IMU (InvenSense)**| Accel + Gyro @ 100Hz | Gravity vector bias < 0.2° | Gravity vector cross-check with floor plane normal |

---

## 3. Demarcation by Ingestion Mode

- **Mode A (Live LiDAR Stream):** Target device iPhone 13 Pro–16 Pro. Latency budget: <= 1.5s per keyframe solve; live preview floor plan updated every 2.0s.
- **Mode B (Live Phone Video Web Capture):** Any iPhone with Safari (iOS 15+). Transmits H.264/WebRTC or JPEG frames over local LAN/WebSocket.
- **Mode C (Offline Batch Upload):** Any supported file upload (Stray Scanner zip, native .MOV/.MP4, photo directory). Maximum reconstruction precision using multi-view fusion and global plane optimization.
