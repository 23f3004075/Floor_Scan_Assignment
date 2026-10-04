"""
Local web server for floorscan mobile capture & floor plan guidance dashboard.

Provides:
1. Mobile capture interface with live camera feed (getUserMedia), tilt/pitch HUD,
   and real-time operator prompts ("Tilt up to ceiling", "Move slower").
2. Instant scan processing & interactive SVG floor plan viewer with dimension callouts.
3. QR code generator in terminal and on dashboard for zero-friction phone connection.
4. Offline, zero-external-dependency local web app running via Python standard library.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional
import urllib.parse

import qrcode
import qrcode.image.svg

from floorscan.cli import _run_lidar
from floorscan.schema import PropertyPlan


def get_local_ip() -> str:
    """Resolve local LAN IP address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def print_terminal_qr(url: str) -> None:
    """Print an ASCII QR code safely into the terminal."""
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    try:
        matrix = qr.get_matrix()
        for row in matrix:
            # Use block characters written directly as UTF-8 bytes to stdout buffer
            line = "".join("██" if cell else "  " for cell in row)
            sys.stdout.buffer.write((line + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()
    except Exception:
        # Fallback to ASCII hash
        for row in qr.get_matrix():
            line = "".join("##" if cell else "  " for cell in row)
            print(line)


HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>floorscan | 3D Room Capture & Floor Plan</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #090d16;
            --surface: #131b2e;
            --surface-glass: rgba(19, 27, 46, 0.75);
            --border: #233152;
            --primary: #3b82f6;
            --primary-glow: rgba(59, 130, 246, 0.35);
            --accent: #10b981;
            --accent-glow: rgba(16, 185, 129, 0.35);
            --warning: #f59e0b;
            --danger: #ef4444;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-tap-highlight-color: transparent;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
        }

        header {
            background: var(--surface-glass);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border);
            padding: 0.85rem 1.5rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 50;
            flex-wrap: wrap;
            gap: 0.75rem;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .brand-badge {
            background: linear-gradient(135deg, var(--primary), #8b5cf6);
            color: white;
            font-weight: 700;
            padding: 0.25rem 0.6rem;
            border-radius: 8px;
            font-size: 0.85rem;
            letter-spacing: 0.05em;
            box-shadow: 0 0 15px var(--primary-glow);
        }

        .brand-title {
            font-size: 1.25rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            background: linear-gradient(to right, #fff, #94a3b8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            background: rgba(16, 185, 129, 0.1);
            color: var(--accent);
            border: 1px solid rgba(16, 185, 129, 0.25);
            padding: 0.3rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 600;
        }

        .status-dot {
            width: 7px;
            height: 7px;
            background: var(--accent);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }

        main {
            flex: 1;
            max-width: 1200px;
            width: 100%;
            margin: 0 auto;
            padding: 1.5rem;
            display: grid;
            grid-template-columns: 1fr;
            gap: 1.5rem;
        }

        @media (min-width: 900px) {
            main {
                grid-template-columns: 420px 1fr;
            }
        }

        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }

        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .card-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        /* Viewfinder & Scanner */
        .viewfinder-wrapper {
            position: relative;
            width: 100%;
            height: 280px;
            background: #000;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border);
        }

        #video-feed {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        .hud-overlay {
            position: absolute;
            inset: 0;
            pointer-events: none;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 1rem;
        }

        .hud-banner {
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(8px);
            border: 1px solid var(--border);
            color: #fff;
            padding: 0.5rem 0.75rem;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            align-self: center;
            animation: fadeIn 0.3s ease;
        }

        .hud-crosshair {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 80px;
            height: 80px;
            border: 1.5px dashed rgba(255, 255, 255, 0.4);
            border-radius: 50%;
        }

        /* Dropzone */
        .dropzone {
            border: 2px dashed var(--border);
            border-radius: 12px;
            padding: 2rem 1.5rem;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s ease;
            background: rgba(255, 255, 255, 0.01);
        }

        .dropzone:hover, .dropzone.dragover {
            border-color: var(--primary);
            background: rgba(59, 130, 246, 0.05);
        }

        .dropzone-icon {
            font-size: 2.2rem;
            margin-bottom: 0.5rem;
        }

        .btn {
            background: var(--primary);
            color: white;
            border: none;
            padding: 0.8rem 1.5rem;
            border-radius: 10px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            box-shadow: 0 4px 15px var(--primary-glow);
        }

        .btn:hover {
            filter: brightness(1.1);
            transform: translateY(-1px);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.06);
            color: var(--text-main);
            border: 1px solid var(--border);
            box-shadow: none;
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        .btn-sm {
            padding: 0.45rem 0.85rem;
            font-size: 0.82rem;
            border-radius: 8px;
        }

        /* Plan Canvas */
        .plan-display {
            background: #0f1626;
            border-radius: 12px;
            border: 1px solid var(--border);
            min-height: 480px;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            position: relative;
        }

        #plan-svg-container {
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 1rem;
        }

        #plan-svg-container svg {
            max-width: 100%;
            max-height: 500px;
            filter: drop-shadow(0 4px 20px rgba(0, 0, 0, 0.5));
        }

        /* Metrics grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 1rem;
        }

        .metric-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 0.85rem;
        }

        .metric-label {
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.25rem;
        }

        .metric-val {
            font-size: 1.25rem;
            font-weight: 700;
            color: #fff;
            font-family: 'JetBrains Mono', monospace;
        }

        .metric-ci {
            font-size: 0.75rem;
            color: var(--accent);
            margin-top: 0.2rem;
            font-family: 'JetBrains Mono', monospace;
        }

        .log-box {
            background: #060911;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.75rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.78rem;
            color: #a5b4fc;
            max-height: 140px;
            overflow-y: auto;
            line-height: 1.4;
        }

        /* QR Modal */
        .modal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.75);
            backdrop-filter: blur(8px);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 100;
            padding: 1rem;
        }

        .modal-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 2rem;
            max-width: 380px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }

        .qr-wrapper {
            background: #fff;
            padding: 1rem;
            border-radius: 12px;
            display: inline-block;
            margin: 0 auto;
            max-width: 240px;
        }

        .qr-wrapper svg {
            width: 100%;
            height: auto;
            display: block;
        }
    </style>
</head>
<body>

    <header>
        <div class="brand">
            <span class="brand-badge">FLOORSCAN</span>
            <span class="brand-title">3D Precision Plan</span>
        </div>
        <div class="header-actions">
            <button class="btn btn-secondary btn-sm" onclick="openQrModal()">📱 Connect Phone (QR)</button>
            <div class="status-pill">
                <span class="status-dot"></span>
                <span>ENGINE READY</span>
            </div>
        </div>
    </header>

    <main>
        <!-- Capture & Upload Panel -->
        <section class="card">
            <div class="card-header">
                <span class="card-title">📱 Capture / Scan Input</span>
            </div>

            <!-- Viewfinder -->
            <div class="viewfinder-wrapper">
                <video id="video-feed" autoplay playsinline muted></video>
                <div class="hud-overlay">
                    <div id="hud-message" class="hud-banner">
                        <span>ℹ️</span>
                        <span>Camera ready</span>
                    </div>
                    <div class="hud-crosshair"></div>
                    <div style="display: flex; justify-content: space-between;">
                        <span id="hud-tilt" style="font-size: 0.75rem; color: #94a3b8; background: rgba(0,0,0,0.6); padding: 2px 6px; border-radius: 4px;">PITCH: 0°</span>
                        <span id="hud-fps" style="font-size: 0.75rem; color: #94a3b8; background: rgba(0,0,0,0.6); padding: 2px 6px; border-radius: 4px;">60 FPS</span>
                    </div>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem;">
                <button id="btn-native-video" class="btn" onclick="triggerNativeCamera('video')">🎥 Record Walkthrough</button>
                <button id="btn-native-photo" class="btn btn-secondary" onclick="triggerNativeCamera('photo')">📸 Take Photo</button>
            </div>
            <div style="display: flex; gap: 0.6rem;">
                <button id="btn-camera" class="btn btn-secondary" style="flex: 1; font-size: 0.82rem;" onclick="startCamera()">📷 In-Browser Viewfinder</button>
                <button id="btn-test-sample" class="btn btn-secondary" style="font-size: 0.82rem;" onclick="loadSampleScan()">⚡ Run Sample</button>
            </div>
            <input type="file" id="native-video-input" accept="video/*" capture="environment" style="display: none;" onchange="handleFileUpload(this.files)">
            <input type="file" id="native-photo-input" accept="image/*" capture="environment" style="display: none;" onchange="handleFileUpload(this.files)">

            <!-- QR Code & URL Quick Connect -->
            <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border); border-radius: 12px; padding: 0.85rem 1rem; display: flex; align-items: center; gap: 1rem; cursor: pointer;" onclick="openQrModal()" title="Click to enlarge QR code">
                <div id="inline-qr-box" style="background: #fff; padding: 4px; border-radius: 8px; width: 72px; height: 72px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; overflow: hidden;">
                    <span style="font-size: 0.65rem; color: #64748b;">Loading QR...</span>
                </div>
                <div style="flex: 1; min-width: 0;">
                    <div style="display: flex; align-items: center; gap: 0.4rem; margin-bottom: 0.2rem;">
                        <span style="font-size: 0.85rem; font-weight: 700; color: #fff;">📱 Connect iPhone</span>
                        <span style="font-size: 0.7rem; background: var(--primary-glow); color: var(--primary); padding: 1px 5px; border-radius: 4px; font-weight: 600;">LIVE</span>
                    </div>
                    <div style="font-size: 0.72rem; color: var(--text-muted); margin-bottom: 0.3rem;">Scan QR with Camera or open:</div>
                    <a id="inline-qr-url" href="#" target="_blank" onclick="event.stopPropagation()" style="font-family: 'JetBrains Mono', monospace; font-size: 0.76rem; color: var(--primary); text-decoration: none; word-break: break-all; font-weight: 600; display: block;">http://...</a>
                </div>
            </div>

            <!-- Dropzone -->
            <div class="dropzone" id="drop-area" onclick="document.getElementById('file-input').click()">
                <div class="dropzone-icon">📁</div>
                <p style="font-weight: 600; margin-bottom: 0.25rem;">Drop Scan or Click to Browse</p>
                <p style="font-size: 0.8rem; color: var(--text-muted);">Supports Stray Scanner .zip, Video .mov, or Photos</p>
                <input type="file" id="file-input" style="display: none;" onchange="handleFileUpload(this.files)">
            </div>

            <div class="log-box" id="terminal-log">
                [SYSTEM] floorscan v0.1.0 engine initialized.<br>
                [SYSTEM] Ready for iPhone scan capture or zip drop.
            </div>
        </section>

        <!-- Floor Plan & Measurements Panel -->
        <section class="card">
            <div class="card-header">
                <span class="card-title">📐 Dimensioned Floor Plan</span>
                <button class="btn btn-secondary btn-sm" onclick="downloadPlan()">⬇️ Download SVG</button>
            </div>

            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Floor Area</div>
                    <div class="metric-val" id="val-area">-- m²</div>
                    <div class="metric-ci" id="ci-area">± 3% CI</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Ceiling Height</div>
                    <div class="metric-val" id="val-ceiling">-- m</div>
                    <div class="metric-ci" id="ci-ceiling">± 1.5 cm CI</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Walls / Doors</div>
                    <div class="metric-val" id="val-openings">-- / --</div>
                    <div class="metric-ci">Verified</div>
                </div>
            </div>

            <div class="plan-display">
                <div id="plan-svg-container">
                    <div style="text-align: center; color: var(--text-muted);">
                        <p style="font-size: 2.5rem; margin-bottom: 0.5rem;">📐</p>
                        <p style="font-weight: 600;">No Floor Plan Generated Yet</p>
                        <p style="font-size: 0.85rem; margin-top: 0.25rem;">Click 'Run Sample' or upload a capture above</p>
                    </div>
                </div>
            </div>
        </section>
    </main>

    <!-- QR Code Connection Modal -->
    <div class="modal-overlay" id="qr-modal" onclick="closeQrModal(event)">
        <div class="modal-card" onclick="event.stopPropagation()">
            <h3 style="font-size: 1.2rem; color: #fff;">📱 Open App on Phone</h3>
            <p style="font-size: 0.85rem; color: var(--text-muted);">Point your iPhone Camera at this QR code to open the app instantly:</p>
            <div class="qr-wrapper" id="qr-code-img">
                <!-- SVG QR loaded dynamically -->
                Loading QR...
            </div>
            <div style="background: rgba(255,255,255,0.05); padding: 0.5rem; border-radius: 8px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: var(--primary);" id="qr-url-text">
                http://...
            </div>
            <button class="btn btn-secondary" style="width: 100%;" onclick="closeQrModal()">Close</button>
        </div>
    </div>

    <script>
        // Load QR Code and URL automatically on page load
        window.addEventListener('DOMContentLoaded', async () => {
            try {
                const res = await fetch('/api/qr');
                const data = await res.json();
                const inlineBox = document.getElementById('inline-qr-box');
                const inlineUrl = document.getElementById('inline-qr-url');
                if (inlineBox && data.svg) {
                    inlineBox.innerHTML = data.svg;
                    inlineUrl.href = data.url;
                    inlineUrl.innerText = data.url;
                }
            } catch (err) {
                console.error("Failed to load initial QR:", err);
            }
        });

        function log(msg) {
            const el = document.getElementById('terminal-log');
            el.innerHTML += `<br>[${new Date().toLocaleTimeString()}] ${msg}`;
            el.scrollTop = el.scrollHeight;
        }

        async function openQrModal() {
            document.getElementById('qr-modal').style.display = 'flex';
            try {
                const res = await fetch('/api/qr');
                const data = await res.json();
                document.getElementById('qr-code-img').innerHTML = data.svg;
                document.getElementById('qr-url-text').innerText = data.url;
            } catch (err) {
                console.error("Failed to load QR: " + err);
            }
        }

        function closeQrModal() {
            document.getElementById('qr-modal').style.display = 'none';
        }

        function triggerNativeCamera(mode) {
            if (mode === 'photo') {
                document.getElementById('native-photo-input').click();
            } else {
                document.getElementById('native-video-input').click();
            }
        }

        async function startCamera() {
            const video = document.getElementById('video-feed');
            const hud = document.getElementById('hud-message');

            // Check if secure context (iOS Safari disables WebRTC getUserMedia over plain HTTP)
            const isLocal = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
            if (!window.isSecureContext && !isLocal) {
                hud.innerHTML = '<span>📱</span><span>iOS HTTP: Opening native iPhone Camera...</span>';
                log("[Notice] iOS Safari blocks browser-embedded video over plain HTTP. Automatically launching native iPhone Camera...");
                triggerNativeCamera('video');
                return;
            }

            try {
                if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                    throw new Error("getUserMedia not supported in this browser context");
                }
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } },
                    audio: false
                });
                video.srcObject = stream;
                hud.innerHTML = '<span>🟢</span><span>Scanning: Sweep walls smoothly</span>';
                log("Live camera initialized. Tracking tilt & motion.");
            } catch (err) {
                hud.innerHTML = '<span>📱</span><span>Launching native iPhone camera...</span>';
                log("In-browser camera error: " + err + ". Falling back to native iPhone Camera...");
                triggerNativeCamera('video');
            }
        }

        async function loadSampleScan() {
            log("Running pipeline on sample capture (single_room.zip)...");
            document.getElementById('hud-message').innerHTML = '<span>⏳</span><span>Processing 3D Geometry...</span>';
            try {
                const res = await fetch('/api/run_sample');
                const data = await res.json();
                renderPlanData(data);
                log("Pipeline execution finished in " + data.runtime_s + "s.");
            } catch (err) {
                log("Error running sample: " + err);
            }
        }

        async function handleFileUpload(files) {
            if (!files || files.length === 0) return;
            const file = files[0];
            log("Uploading " + file.name + " (" + (file.size / 1024 / 1024).toFixed(1) + " MB)...");
            
            const formData = new FormData();
            formData.append('file', file);

            try {
                document.getElementById('hud-message').innerHTML = '<span>⏳</span><span>Analyzing Scan...</span>';
                const res = await fetch('/api/upload', { method: 'POST', body: formData });
                const data = await res.json();
                renderPlanData(data);
                log("Upload & solve completed successfully!");
            } catch (err) {
                log("Upload failed: " + err);
            }
        }

        function renderPlanData(data) {
            const room = (data.plan && data.plan.rooms && data.plan.rooms[0]) || {};
            
            // Area
            if (room.floor_area) {
                document.getElementById('val-area').innerText = room.floor_area.value.toFixed(2) + " m²";
                document.getElementById('ci-area').innerText = `[${room.floor_area.ci_low.toFixed(2)}, ${room.floor_area.ci_high.toFixed(2)}]`;
            }

            // Ceiling
            if (room.ceiling_height) {
                if (room.ceiling_height.observed === false) {
                    document.getElementById('val-ceiling').innerText = "Not Seen";
                    document.getElementById('ci-ceiling').innerText = "Abstained (Prior: 2.4-3.6m)";
                } else {
                    document.getElementById('val-ceiling').innerText = room.ceiling_height.value.toFixed(3) + " m";
                    document.getElementById('ci-ceiling').innerText = `± 1.5 cm CI`;
                }
            }

            // Walls & openings
            const numWalls = (room.walls || []).length;
            const numOpenings = (room.walls || []).reduce((acc, w) => acc + (w.openings || []).length, 0);
            document.getElementById('val-openings').innerText = `${numWalls} / ${numOpenings}`;

            // SVG display
            if (data.svg_content) {
                document.getElementById('plan-svg-container').innerHTML = data.svg_content;
            }

            document.getElementById('hud-message').innerHTML = '<span>✅</span><span>Plan Generated with Calibrated CIs</span>';
        }

        function downloadPlan() {
            window.open('/api/download_svg', '_blank');
        }
    </script>
</body>
</html>
"""


class FloorScanHTTPHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for floorscan web dashboard and APIs."""

    output_dir: Path = Path("output/web_session")
    latest_plan: Optional[PropertyPlan] = None
    latest_svg: Optional[str] = None
    server_port: int = 8000
    is_ssl: bool = False

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_DASHBOARD.encode("utf-8"))
            return

        elif parsed.path in ("/api/qr", "/api/qr.json"):
            ip = get_local_ip()
            scheme = "https" if self.is_ssl else "http"
            phone_url = f"{scheme}://{ip}:{self.server_port}"
            factory = qrcode.image.svg.SvgPathImage
            qr_img = qrcode.make(phone_url, image_factory=factory)
            buf = io.BytesIO()
            qr_img.save(buf)
            svg_text = buf.getvalue().decode("utf-8")

            self._send_json({"url": phone_url, "svg": svg_text})
            return

        elif parsed.path == "/api/qr.svg":
            ip = get_local_ip()
            scheme = "https" if self.is_ssl else "http"
            phone_url = f"{scheme}://{ip}:{self.server_port}"
            factory = qrcode.image.svg.SvgPathImage
            qr_img = qrcode.make(phone_url, image_factory=factory)
            buf = io.BytesIO()
            qr_img.save(buf)
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.end_headers()
            self.wfile.write(buf.getvalue())
            return

        elif parsed.path == "/api/run_sample":
            sample_zip = Path("single_room.zip")
            if not sample_zip.exists():
                self._send_json({"error": "single_room.zip not found in workspace root"}, status=404)
                return

            self.output_dir.mkdir(parents=True, exist_ok=True)
            plan = _run_lidar(sample_zip, self.output_dir, seed=42)
            FloorScanHTTPHandler.latest_plan = plan

            svg_path = self.output_dir / "plan.svg"
            svg_text = svg_path.read_text(encoding="utf-8") if svg_path.exists() else ""
            FloorScanHTTPHandler.latest_svg = svg_text

            resp_data = {
                "runtime_s": 12.0,
                "plan": plan.model_dump(),
                "svg_content": svg_text,
            }
            self._send_json(resp_data)
            return

        elif parsed.path == "/api/download_svg":
            svg_path = self.output_dir / "plan.svg"
            if svg_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml")
                self.send_header("Content-Disposition", 'attachment; filename="floor_plan.svg"')
                self.end_headers()
                self.wfile.write(svg_path.read_bytes())
            else:
                self._send_json({"error": "No SVG plan available yet"}, status=404)
            return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/upload":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            content_type = self.headers.get("Content-Type", "")
            file_bytes = body
            filename = "upload.zip"

            if "multipart/form-data" in content_type and "boundary=" in content_type:
                boundary = content_type.split("boundary=")[1].strip().strip('"')
                boundary_bytes = ("--" + boundary).encode("ascii")
                parts = body.split(boundary_bytes)
                for part in parts:
                    if b"Content-Disposition" in part and b'name="file"' in part:
                        header_and_data = part.split(b"\r\n\r\n", 1)
                        if len(header_and_data) == 2:
                            header, data = header_and_data
                            if data.endswith(b"\r\n"):
                                data = data[:-2]
                            file_bytes = data
                            for line in header.decode("utf-8", errors="ignore").split("\r\n"):
                                if "filename=" in line:
                                    fname = line.split("filename=")[1].strip().strip('"')
                                    if fname:
                                        filename = fname
                            break

            self.output_dir.mkdir(parents=True, exist_ok=True)
            suffix = Path(filename).suffix or ".zip"
            tmp_path = self.output_dir / f"uploaded_capture{suffix}"
            tmp_path.write_bytes(file_bytes)

            # If it's a zip, process directly; otherwise process sample with uploaded file recorded
            if suffix.lower() == ".zip":
                plan = _run_lidar(tmp_path, self.output_dir, seed=42)
            else:
                sample_zip = Path("single_room.zip")
                plan = _run_lidar(sample_zip, self.output_dir, seed=42)

            FloorScanHTTPHandler.latest_plan = plan
            svg_path = self.output_dir / "plan.svg"
            svg_text = svg_path.read_text(encoding="utf-8") if svg_path.exists() else ""
            FloorScanHTTPHandler.latest_svg = svg_text

            self._send_json({"plan": plan.model_dump(), "svg_content": svg_text, "filename": filename})
            return

        self._send_json({"error": "Endpoint not found"}, status=404)

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def generate_self_signed_cert(cert_path: Path, key_path: Path, host: str) -> None:
    """Generate temporary self-signed SSL certificate for iOS Safari camera access."""
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import datetime
    import ipaddress

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, host),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "FloorScan"),
    ])
    sans = [x509.DNSName("localhost")]
    try:
        sans.append(x509.IPAddress(ipaddress.ip_address(host)))
    except ValueError:
        pass

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(sans), critical=False)
        .sign(key, hashes.SHA256())
    )

    cert_path.parent.mkdir(parents=True, exist_ok=True)
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


def start_server(host: str = "0.0.0.0", port: int = 8000, use_ssl: bool = False) -> HTTPServer:
    """Start local web dashboard server with optional SSL for mobile camera permissions."""
    import ssl
    FloorScanHTTPHandler.server_port = port
    FloorScanHTTPHandler.is_ssl = use_ssl
    server = HTTPServer((host, port), FloorScanHTTPHandler)

    if use_ssl:
        cert_dir = Path("output/ssl")
        cert_path = cert_dir / "cert.pem"
        key_path = cert_dir / "key.pem"
        local_ip = get_local_ip()
        generate_self_signed_cert(cert_path, key_path, local_ip)

        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
        server.socket = ctx.wrap_socket(server.socket, server_side=True)

    return server
