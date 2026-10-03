"""
Gravity estimation and camera-axis convention detection.

Two conventions are tested:
  - OpenCV-style: camera x-right, y-down, z-forward (pose R columns map these to world)
  - ARKit-style: camera x-right, y-up, z-backward

The correct one is chosen by which produces a sharper floor-plane height peak
in the back-projected point cloud. The sharper peak = correct convention.

Also estimates the global Manhattan yaw (dominant horizontal direction).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.stats import mode as scipy_mode

from floorscan.io.stray_scanner import StrayCapture, Frame


# ---------------------------------------------------------------------------
# Scene evidence (the shared structure downstream modules consume)
# ---------------------------------------------------------------------------

@dataclass
class SceneEvidence:
    """
    Gravity-aligned, metric scene evidence from a capture.
    All downstream geometry modules consume this.
    """
    # Point cloud in gravity-aligned world frame (N, 3)
    points: np.ndarray
    # Per-point color if available (N, 3) uint8 BGR
    colors: Optional[np.ndarray] = None
    # Per-point source frame index (N,)
    point_frame_ids: Optional[np.ndarray] = None
    # Corrected poses (list of 4x4 matrices)
    poses: list[np.ndarray] = field(default_factory=list)
    # Per-frame intrinsics (depth resolution)
    intrinsics: list = field(default_factory=list)
    # Gravity direction in world frame (unit vector, points down)
    gravity: np.ndarray = field(default_factory=lambda: np.array([0, -1, 0]))
    # Convention used: "opencv" or "arkit"
    convention: str = ""
    # Global Manhattan yaw (radians, rotation of dominant wall direction from world x-axis)
    manhattan_yaw: float = 0.0
    # Floor height in world frame (metres, along gravity axis)
    floor_height_initial: float = 0.0
    # Capture metadata
    capture_id: str = ""
    duration_s: float = 0.0
    num_frames_used: int = 0
    # Frames (kept for opening detection, RGB access, etc.)
    frames: list[Frame] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Back-projection
# ---------------------------------------------------------------------------

def backproject_depth(
    depth: np.ndarray,
    intrinsics_matrix: np.ndarray,
    pose: np.ndarray,
    camera_axes: str = "opencv",
) -> np.ndarray:
    """
    Back-project a depth map to 3D world coordinates.

    Args:
        depth: (H, W) float32 depth in metres. Zero = invalid.
        intrinsics_matrix: 3x3 camera intrinsics (at depth resolution).
        pose: 4x4 camera-to-world transform.
        camera_axes: "opencv" (x-right, y-down, z-forward) or "arkit" (x-right, y-up, z-backward).

    Returns:
        (N, 3) array of valid 3D points in world frame.
    """
    H, W = depth.shape
    valid = depth > 0
    v_indices, u_indices = np.where(valid)
    d = depth[valid]

    fx = intrinsics_matrix[0, 0]
    fy = intrinsics_matrix[1, 1]
    cx = intrinsics_matrix[0, 2]
    cy = intrinsics_matrix[1, 2]

    # Camera-frame coordinates
    x_cam = (u_indices.astype(np.float64) - cx) * d / fx
    y_cam = (v_indices.astype(np.float64) - cy) * d / fy
    z_cam = d.astype(np.float64)

    if camera_axes == "opencv":
        # OpenCV: x-right, y-down, z-forward
        points_cam = np.stack([x_cam, y_cam, z_cam], axis=-1)
    elif camera_axes == "arkit":
        # ARKit: x-right, y-up, z-backward
        points_cam = np.stack([x_cam, -y_cam, -z_cam], axis=-1)
    else:
        raise ValueError(f"Unknown camera axes: {camera_axes}")

    # Transform to world
    R = pose[:3, :3]
    t = pose[:3, 3]
    points_world = (R @ points_cam.T).T + t

    return points_world.astype(np.float32)


# ---------------------------------------------------------------------------
# Convention detection
# ---------------------------------------------------------------------------

def _floor_peak_sharpness(heights: np.ndarray, bin_width: float = 0.01) -> tuple[float, float]:
    """
    Compute the sharpness of the floor-plane height peak.

    Returns (peak_count_fraction, peak_height):
        peak_count_fraction: fraction of points in the modal 1-cm bin
        peak_height: height of the modal bin center
    """
    if len(heights) == 0:
        return 0.0, 0.0

    h_min, h_max = np.percentile(heights, [1, 99])
    bins = np.arange(h_min, h_max + bin_width, bin_width)
    if len(bins) < 2:
        return 0.0, 0.0

    counts, edges = np.histogram(heights, bins=bins)
    peak_idx = np.argmax(counts)
    peak_count = counts[peak_idx]
    peak_height = (edges[peak_idx] + edges[peak_idx + 1]) / 2.0
    peak_fraction = peak_count / len(heights)

    return peak_fraction, peak_height


def detect_convention(
    capture: StrayCapture,
    sample_stride: int = 10,
    max_sample_frames: int = 50,
) -> tuple[str, float, float]:
    """
    Auto-detect camera axis convention by testing which gives a sharper floor peak.

    Args:
        capture: Loaded Stray Scanner capture.
        sample_stride: Stride for frame sampling.
        max_sample_frames: Maximum frames to sample.

    Returns:
        (convention, peak_fraction, floor_height):
            convention: "opencv" or "arkit"
            peak_fraction: fraction of points in the floor bin (higher = sharper)
            floor_height: estimated floor height in world frame
    """
    # Sample frames
    frames_with_depth = [f for f in capture.frames if f.depth is not None]
    sampled = frames_with_depth[::sample_stride][:max_sample_frames]

    if not sampled:
        raise ValueError("No frames with depth available for convention detection")

    results = {}
    for convention in ["opencv", "arkit"]:
        all_points = []
        for frame in sampled:
            K_depth = frame.intrinsics_depth.to_matrix()
            pts = backproject_depth(frame.depth, K_depth, frame.pose, camera_axes=convention)
            all_points.append(pts)

        all_points = np.concatenate(all_points, axis=0)

        # For y-up world, heights are the y-coordinate
        # For the convention test, we try both and see which gives a sharper floor
        # In y-up world, floor is at the minimum y (most negative y)
        heights = all_points[:, 1]  # y-axis = vertical in y-up world
        sharpness, floor_h = _floor_peak_sharpness(heights)
        results[convention] = (sharpness, floor_h, len(all_points))

    # Pick the convention with the sharper floor peak
    opencv_sharp = results["opencv"][0]
    arkit_sharp = results["arkit"][0]

    if opencv_sharp > arkit_sharp:
        chosen = "opencv"
    elif arkit_sharp > opencv_sharp:
        chosen = "arkit"
    else:
        # Ambiguous: default to opencv (more common for Stray Scanner)
        chosen = "opencv"

    peak_frac = results[chosen][0]
    floor_h = results[chosen][1]

    return chosen, peak_frac, floor_h


# ---------------------------------------------------------------------------
# Manhattan yaw estimation
# ---------------------------------------------------------------------------

def estimate_manhattan_yaw(points: np.ndarray, gravity_axis: int = 1) -> float:
    """
    Estimate the global Manhattan yaw from a point cloud.

    Finds the dominant horizontal direction by analysing the distribution of
    horizontal point-pair angles (horizontal = perpendicular to gravity).

    Args:
        points: (N, 3) point cloud.
        gravity_axis: which axis is gravity (1 = y-up).

    Returns:
        Yaw angle in radians (rotation from world x-axis to dominant wall direction).
    """
    # Project to horizontal plane
    if gravity_axis == 1:
        horiz = points[:, [0, 2]]  # x, z
    else:
        horiz = points[:, [0, 1]]  # fallback

    # Subsample for speed
    if len(horiz) > 10000:
        rng = np.random.RandomState(42)
        idx = rng.choice(len(horiz), 10000, replace=False)
        horiz = horiz[idx]

    # Compute pairwise angles of nearby points
    from scipy.spatial import cKDTree
    tree = cKDTree(horiz)
    # For each point, find the nearest neighbor
    _, nn_idx = tree.query(horiz, k=2)
    nn_idx = nn_idx[:, 1]  # skip self

    diffs = horiz[nn_idx] - horiz
    angles = np.arctan2(diffs[:, 1], diffs[:, 0])

    # Fold angles into [0, pi/2) (Manhattan = 4-fold symmetry)
    angles_folded = angles % (np.pi / 2)

    # Histogram to find the peak
    bins = np.linspace(0, np.pi / 2, 181)  # 0.5-degree bins
    counts, edges = np.histogram(angles_folded, bins=bins)
    peak_idx = np.argmax(counts)
    yaw = (edges[peak_idx] + edges[peak_idx + 1]) / 2.0

    return float(yaw)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def estimate_gravity_and_convention(
    capture: StrayCapture,
    seed: int = 42,
    frame_stride: int = 4,
    max_frames: int = 300,
) -> SceneEvidence:
    """
    Full gravity/convention pipeline:
    1. Auto-detect camera axis convention (opencv vs arkit).
    2. Back-project all selected frames to a point cloud.
    3. Estimate Manhattan yaw.
    4. Return SceneEvidence ready for geometry core.

    Args:
        capture: Loaded Stray Scanner capture.
        seed: Random seed.
        frame_stride: Stride for selecting frames for the full point cloud.
        max_frames: Maximum frames for the full point cloud.

    Returns:
        SceneEvidence with gravity-aligned point cloud.
    """
    np.random.seed(seed)

    # Step 1: Detect convention
    convention, peak_frac, floor_h = detect_convention(capture)

    # Step 2: Build full point cloud with the chosen convention
    frames_with_depth = [f for f in capture.frames if f.depth is not None]
    selected_frames = frames_with_depth[::frame_stride][:max_frames]

    all_points = []
    all_frame_ids = []
    for frame in selected_frames:
        K_depth = frame.intrinsics_depth.to_matrix()
        pts = backproject_depth(frame.depth, K_depth, frame.pose, camera_axes=convention)
        all_points.append(pts)
        all_frame_ids.append(np.full(len(pts), frame.index, dtype=np.int32))

    points = np.concatenate(all_points, axis=0)
    frame_ids = np.concatenate(all_frame_ids, axis=0)

    # Step 3: Estimate Manhattan yaw
    manhattan_yaw = estimate_manhattan_yaw(points)

    # Step 4: Build SceneEvidence
    scene = SceneEvidence(
        points=points,
        point_frame_ids=frame_ids,
        poses=[f.pose for f in selected_frames],
        intrinsics=[f.intrinsics_depth for f in selected_frames],
        gravity=np.array([0, -1, 0]),  # y-up world, gravity points down
        convention=convention,
        manhattan_yaw=manhattan_yaw,
        floor_height_initial=floor_h,
        capture_id=capture.capture_id,
        duration_s=capture.duration_s,
        num_frames_used=len(selected_frames),
        frames=selected_frames,
    )

    return scene
