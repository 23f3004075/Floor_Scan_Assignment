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

### Starting the Server:
```bash
python -m floorscan.cli serve
```

When started, `floorscan` automatically resolves your laptop's local IP address and displays:
1. **Laptop URL:** `http://localhost:8000`
2. **Phone URL:** `http://<your-ip>:8000` (e.g. `http://192.168.0.194:8000`)
3. **Scannable Terminal QR Code:** Point your iPhone camera directly at your laptop's terminal to open the app instantly without typing any IP address!
4. **Dashboard QR Button:** If viewing on your laptop browser, click the **"📱 Connect Phone (QR)"** button in the top navigation bar to open a QR code popup.

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

You can use your iPhone with `floorscan` in two convenient ways:

---

### Method A: Live Mobile Web App (Zero Install - Works in Safari)

Use this mode on any iPhone (iPhone 11 through 16 Pro):

1. **Start the local server on your PC:**
   ```bash
   python -m floorscan.cli serve
   ```
2. **Find your PC's local IP address:**
   - In Windows PowerShell, run: `ipconfig` (look for `IPv4 Address`, e.g. `192.168.1.45`).
   - In Mac/Linux terminal, run: `ifconfig` or `ip a`.
3. **Open Safari on your iPhone:**
   - Make sure your iPhone is connected to the **same Wi-Fi network** as your laptop.
   - Type into Safari: `http://<your-laptop-ip>:8000` (e.g. `http://192.168.1.45:8000`).
4. **Scan the Room:**
   - Tap **"Open Camera"** and grant camera permissions.
   - The HUD will show you live pitch angle and real-time guidance prompts (`"TILT UP: Sweep up to ceiling"`, `"SLOW DOWN: Moving too fast"`, `"TOO CLOSE"`).
   - You can also upload any recorded `.mov` video or photos directly from your phone.
   - Instantly view and download the dimensioned vector floor plan (`plan.svg`) on your phone!

---

### Method B: High-Precision LiDAR Capture (Stray Scanner App)

For sub-centimeter accuracy on **iPhone Pro models (12 Pro, 13 Pro, 14 Pro, 15 Pro, 16 Pro) or iPad Pro**:

1. **Install Stray Scanner:**
   - Download the free **[Stray Scanner](https://apps.apple.com/app/stray-scanner/id1557051662)** app from the App Store.
2. **Capture Procedure (60 Seconds):**
   - Stand at the primary room doorway. Tap **Record**.
   - Walk slowly (~0.3 m/s) clockwise around the room perimeter at chest height.
   - **Crucial Step (The Ceiling Sweep):** In the middle of the room, slowly tilt your phone up 60°–75° towards the ceiling, hold for 2 seconds to capture the ceiling plane, then tilt back down.
   - Complete the perimeter loop and return to the starting doorway threshold. Tap **Stop**.
3. **Export to PC:**
   - Tap **Share / Export** in Stray Scanner.
   - AirDrop, email, or Google Drive the resulting `.zip` folder to your laptop.
4. **Process with floorscan:**
   - Drag and drop the `.zip` file into the web dashboard at `http://localhost:8000`, **OR**
   - Run via terminal:
     ```bash
     python -m floorscan.cli run <your_scan.zip> --out output/my_scan
     ```
   The engine automatically corrects ARKit odometry drift, fits wall and ceiling planes, detects doors/windows, evaluates damage, and exports `plan.json` and `plan.svg`.

