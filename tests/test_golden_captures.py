"""
Golden tests verifying deterministic ingestion, convention auto-detection,
floor height recovery, and honest ceiling abstention on real iPhone LiDAR captures.
"""

from pathlib import Path
import pytest
from floorscan.io.stray_scanner import load_stray_capture
from floorscan.geometry.gravity import estimate_gravity_and_convention
from floorscan.geometry.planes import fit_floor_ceiling_planes


def test_single_room_golden():
    """Verify single_room.zip capture properties."""
    zip_path = Path("single_room.zip")
    if not zip_path.exists():
        pytest.skip("single_room.zip not found")

    capture = load_stray_capture(zip_path, max_frames=300)
    assert len(capture.frames) > 0
    assert capture.capture_id == "c00a170fe1"

    scene = estimate_gravity_and_convention(capture, seed=42)
    # OpenCV convention must be chosen with sharp floor peak
    assert scene.convention == "opencv"

    planes = fit_floor_ceiling_planes(scene)
    # Floor height should be around -1.47m
    assert planes.floor_height == pytest.approx(-1.47, abs=0.05)
    # Ceiling MUST honestly abstain
    assert not planes.ceiling_observed
    assert planes.ceiling_plane is None
