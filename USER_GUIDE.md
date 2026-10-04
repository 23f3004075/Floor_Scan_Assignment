# floorscan: User Guide & Startup Manual

A complete, step-by-step guide on how to launch, configure, and use `floorscan`—both via the **interactive web dashboard** and via the **high-performance CLI**.

---

## 📑 Table of Contents

1. [System Prerequisites & Installation](#1-system-prerequisites--installation)
2. [Starting the Interactive Web Dashboard (`floorscan serve`)](#2-starting-the-interactive-web-dashboard)
3. [Running Scans via CLI (`floorscan run`)](#3-running-scans-via-cli)
4. [Running Live Stream Simulation (`floorscan live`)](#4-running-live-stream-simulation)
5. [Reproducing Benchmarks & Fix Loops](#5-reproducing-benchmarks--fix-loops)
6. [Understanding the Output Files](#6-understanding-the-output-files)
7. [Scanning New Rooms with Your iPhone](#7-scanning-new-rooms-with-your-iphone)

---

## 1. System Prerequisites & Installation

### Requirements
- **OS:** Windows 10/11, macOS, or Linux
- **Python:** Version `3.10` or higher
- **Hardware:** Consumer laptop or workstation (runs 100% offline, CPU-friendly)

### Installation
Open your terminal (PowerShell or Bash) in the project directory:

```bash
# 1. Navigate to workspace
cd "d:\PERSONAL PROJECTS\room_scan"

# 2. Install floorscan in editable mode
pip install -e .

# 3. Verify installation
python -m floorscan.cli --help
```

You will see the available CLI commands: `run`, `serve`, `live`, `bench`, `ablate-drift`, `fixloop`, `repro`, and `schema`.

---

## 2. Starting the Interactive Web Dashboard

To launch the web interface with live camera viewfinder, real-time guidance prompts, drag-and-drop processing, and vector SVG floor plan viewer:

```bash
python -m floorscan.cli serve
```

### Accessing the Dashboard:
1. Open your browser and navigate to:  
   👉 **`http://localhost:8000`**
2. **On your iPhone (same Wi-Fi network):**  
   Find your laptop's local IP address (e.g. `192.168.1.15`), and navigate to `http://192.168.1.15:8000` on mobile Safari.

### Dashboard Features:
- **⚡ Run Sample:** Click the button to immediately run `single_room.zip` through the pipeline and view the generated floor plan with wall dimensions, floor area, and ceiling height in real time.
- **📁 Drag-and-Drop Uploader:** Drop any Stray Scanner `.zip`, video file, or photo folder to process it automatically.
- **📷 Camera Viewfinder:** Tap "Open Camera" to activate your device camera with live tilt/pitch HUD overlays and real-time guidance prompts ("Tilt up to ceiling", "Slow down", "Scanning...").
- **📐 Interactive Dimensioned Plan:** View the clean vector SVG floor plan with room boundaries, wall lengths, and confidence intervals. Click **"Download SVG"** to export.

---

## 3. Running Scans via CLI (`floorscan run`)

The pipeline supports one single command to process any room capture with automatic tier detection:

```bash
# Process a LiDAR Stray Scanner capture (.zip or folder)
python -m floorscan.cli run single_room.zip --out output/my_scan
```

### Other Included Sample Captures to Try:
```bash
# Test floor-only scan (accurately abstains from unobserved ceiling)
python -m floorscan.cli run single_scan_floor_only.zip --out output/scan_floor_only

# Test scan with full ceiling sweep (directly measures 2.102m ceiling ± 1.5 cm)
python -m floorscan.cli run single_scan_with_ceiling.zip --out output/scan_with_ceiling
```

### Summary Output Example:
```
                         Floor Plan Summary                         
┌──────────┬───────────────────────────────────────────────────────┐
│ Property │ Value                                                 │
├──────────┼───────────────────────────────────────────────────────┤
│ Tier     │ lidar                                                 │
│ Rooms    │ 1                                                     │
│   Room 1 │ 12 walls, 0 openings, ceiling: not_observed           │
│ Runtime  │ 12.1s                                                 │
└──────────┴───────────────────────────────────────────────────────┘
[OK] plan.json written to output\my_scan\plan.json
```

---

## 4. Running Live Stream Simulation (`floorscan live`)

To simulate live streaming data from an iPhone with real-time operator guidance and a deterministic final solve upon scan completion:

```bash
python -m floorscan.cli live --source replay:single_room.zip --out output/live_session
```

This will stream frames, compute real-time guidance signals (checking floor visibility, ceiling tilt, movement speed, and proximity to walls), output warnings to the terminal, and solve the final floor plan on scan completion.

---

## 5. Reproducing Benchmarks & Fix Loops

All reported metrics can be verified cold from raw inputs:

```bash
# 1. Full reproduction suite (reproduces all numbers cold from raw data)
python -m floorscan.cli repro

# 2. Benchmark gate evaluation against analytical ground truth
python -m floorscan.cli bench

# 3. Drift correction ablation (re-anchoring ON vs OFF)
python -m floorscan.cli ablate-drift --input-path single_room.zip

# 4. Fix-loop before/after verification table
python -m floorscan.cli fixloop

# 5. Run automated test suite
pytest tests/
```

---

## 6. Understanding the Output Files

Every run creates three primary files in your output directory:

### 1. `plan.json`
The complete, machine-readable property plan adhering to the schema. Every single measurement includes a calibrated 90% confidence interval:
```json
{
  "property_id": "scan_001",
  "tier": "lidar",
  "rooms": [
    {
      "room_id": "room_1",
      "room_name": "Room 1",
      "floor_area": {
        "value": 23.85,
        "ci_low": 23.13,
        "ci_high": 24.56,
        "confidence_level": "high",
        "method": "polygon_area"
      },
      "ceiling_height": {
        "observed": false,
        "reason": "Only 0 points in ceiling range, below minimum 500",
        "prior_low": 2.4,
        "prior_high": 3.6,
        "confidence_level": "not_observed"
      },
      "walls": [ ... ],
      "damage_regions": [ ... ],
      "concealed_damage_flags": [ ... ],
      "scope_items": [ ... ]
    }
  ]
}
```

### 2. `plan.svg`
A presentation-grade vector floor plan showing:
- Dark-mode, architectural room footprint.
- Wall dimension labels with metric lengths.
- Door and window openings.
- Metric scale bar (1 m and 2 m references) and North arrow orientation.

### 3. `run_manifest.json`
Audit trail recording the exact version, random seeds, execution duration, and inputs used to ensure determinism and compliance.

---

## 7. Scanning New Rooms with Your iPhone

For best results when scanning an unseen physical space, follow the [Operator Capture Protocol](docs/capture_protocol.md):

1. **App:** Use **Stray Scanner** (free on iOS App Store) on an iPhone 12 Pro–16 Pro or iPad Pro.
2. **Perimeter Loop:** Stand at the room door, tap record, walk slowly (~0.3 m/s) around the perimeter clockwise at chest height.
3. **The Ceiling Sweep (Crucial):** At the center of the room, slowly tilt up towards the ceiling, sweep across the ceiling line, and tilt back down.
4. **Loop Closure:** Always return to the starting doorway threshold before stopping the scan.
5. **Transfer:** AirDrop or copy the exported `.zip` folder to your laptop and run:
   ```bash
   python -m floorscan.cli run <your_scan.zip> --out output/my_room
   ```
