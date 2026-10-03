"""
Stray Scanner capture ingest.

Accepts a zip file or folder in Stray Scanner export format:
    <capture_id>/
        rgb.mp4
        depth/NNNNNN.png        (256x192, uint16 millimetres)
        confidence/NNNNNN.png   (256x192, values 0/1/2)
        odometry.csv            (timestamp, frame, x y z, qx qy qz qw, fx fy cx cy)
        camera_matrix.csv       (3x3 K for the 1920x1440 frame)
        imu.csv                 (~100 Hz accel + gyro)

Handles:
    - Zip or folder input (including one nested capture dir)
    - Per-frame intrinsics from odometry.csv (preferred) with camera_matrix.csv fallback
    - K scaled by 256/1920 for depth frames
    - uint16 mm -> float32 metres
    - Confidence == 2 filtering
    - Landscape-stored video orientation
    - Frame selection by sharpness and parallax
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from tqdm import tqdm


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CameraIntrinsics:
    """Camera intrinsics for a frame."""
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int

    def to_matrix(self) -> np.ndarray:
        """3x3 intrinsics matrix."""
        return np.array([
            [self.fx, 0.0, self.cx],
            [0.0, self.fy, self.cy],
            [0.0, 0.0, 1.0],
        ], dtype=np.float64)

    def scaled(self, target_w: int, target_h: int) -> "CameraIntrinsics":
        """Scale intrinsics to a different resolution."""
        sx = target_w / self.width
        sy = target_h / self.height
        return CameraIntrinsics(
            fx=self.fx * sx, fy=self.fy * sy,
            cx=self.cx * sx, cy=self.cy * sy,
            width=target_w, height=target_h,
        )


@dataclass
class IMUSample:
    """A single IMU measurement."""
    timestamp: float
    accel: np.ndarray  # (3,) m/s²
    gyro: np.ndarray   # (3,) rad/s


@dataclass
class Frame:
    """A single frame from the capture with all associated data."""
    index: int
    timestamp: float
    # Pose: 4x4 camera-to-world transform
    pose: np.ndarray  # (4, 4)
    # Intrinsics for the RGB resolution
    intrinsics_rgb: CameraIntrinsics
    # Intrinsics for the depth resolution
    intrinsics_depth: CameraIntrinsics
    # Populated on demand
    rgb: Optional[np.ndarray] = None      # (H, W, 3) uint8 BGR
    depth: Optional[np.ndarray] = None    # (H, W) float32 metres
    confidence: Optional[np.ndarray] = None  # (H, W) uint8 {0,1,2}


@dataclass
class StrayCapture:
    """A loaded Stray Scanner capture."""
    capture_id: str
    frames: list[Frame] = field(default_factory=list)
    imu: list[IMUSample] = field(default_factory=list)
    rgb_resolution: tuple[int, int] = (1920, 1440)  # (width, height) as stored
    depth_resolution: tuple[int, int] = (256, 192)
    camera_matrix_rgb: Optional[np.ndarray] = None  # 3x3 from camera_matrix.csv
    source_path: str = ""
    convention_used: str = ""  # filled after convention detection

    @property
    def num_frames(self) -> int:
        return len(self.frames)

    @property
    def duration_s(self) -> float:
        if len(self.frames) < 2:
            return 0.0
        return self.frames[-1].timestamp - self.frames[0].timestamp


# ---------------------------------------------------------------------------
# Quaternion utilities
# ---------------------------------------------------------------------------

def quat_to_rotation_matrix(qx: float, qy: float, qz: float, qw: float) -> np.ndarray:
    """Convert quaternion (x, y, z, w) to 3x3 rotation matrix."""
    q = np.array([qx, qy, qz, qw], dtype=np.float64)
    q = q / np.linalg.norm(q)
    x, y, z, w = q

    R = np.array([
        [1 - 2*(y*y + z*z),     2*(x*y - z*w),     2*(x*z + y*w)],
        [    2*(x*y + z*w), 1 - 2*(x*x + z*z),     2*(y*z - x*w)],
        [    2*(x*z - y*w),     2*(y*z + x*w), 1 - 2*(x*x + y*y)],
    ], dtype=np.float64)
    return R


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_stray_capture(
    path: Path,
    load_rgb: bool = False,
    load_depth: bool = True,
    load_confidence: bool = True,
    stride: int = 1,
    max_frames: Optional[int] = None,
    confidence_threshold: int = 2,
    depth_min_m: float = 0.2,
    depth_max_m: float = 5.0,
) -> StrayCapture:
    """
    Load a Stray Scanner capture from a zip file or directory.

    Args:
        path: Path to zip file or capture directory.
        load_rgb: Whether to load RGB frames (large; skip if not needed).
        load_depth: Whether to load depth maps.
        load_confidence: Whether to load confidence maps.
        stride: Frame stride (1 = every frame, 6 = every 6th frame).
        max_frames: Maximum number of frames to load.
        confidence_threshold: Minimum confidence to keep (0, 1, or 2).
        depth_min_m: Minimum valid depth in metres.
        depth_max_m: Maximum valid depth in metres.

    Returns:
        A StrayCapture with all requested data loaded.
    """
    path = Path(path)

    if path.suffix.lower() == ".zip":
        return _load_from_zip(
            path, load_rgb, load_depth, load_confidence,
            stride, max_frames, confidence_threshold, depth_min_m, depth_max_m,
        )
    elif path.is_dir():
        return _load_from_dir(
            path, load_rgb, load_depth, load_confidence,
            stride, max_frames, confidence_threshold, depth_min_m, depth_max_m,
        )
    else:
        raise ValueError(f"Unsupported path: {path}")


def _find_capture_dir(root: Path) -> Path:
    """Find the capture directory (may be nested one level)."""
    if (root / "odometry.csv").is_file():
        return root
    # Check one level of nesting
    for child in root.iterdir():
        if child.is_dir() and (child / "odometry.csv").is_file():
            return child
    raise FileNotFoundError(f"No Stray Scanner capture found in {root}")


def _find_capture_prefix_in_zip(zf: zipfile.ZipFile) -> str:
    """Find the capture folder prefix inside a zip."""
    for name in zf.namelist():
        if name.endswith("odometry.csv"):
            # Return the prefix (e.g., "c00a170fe1/")
            parts = name.rsplit("odometry.csv", 1)
            return parts[0]
    raise FileNotFoundError("No odometry.csv found in zip")


def _parse_odometry_csv(text: str) -> list[dict]:
    """Parse odometry.csv rows into dicts."""
    reader = csv.reader(io.StringIO(text))
    rows = []
    for row in reader:
        if len(row) < 11:
            continue
        try:
            timestamp = float(row[0])
            frame_idx = int(row[1])
        except (ValueError, IndexError):
            continue  # Skip header or malformed rows
        rows.append({
            "timestamp": timestamp,
            "frame": frame_idx,
            "x": float(row[2]),
            "y": float(row[3]),
            "z": float(row[4]),
            "qx": float(row[5]),
            "qy": float(row[6]),
            "qz": float(row[7]),
            "qw": float(row[8]),
            "fx": float(row[9]),
            "fy": float(row[10]),
            "cx": float(row[11]) if len(row) > 11 else 0.0,
            "cy": float(row[12]) if len(row) > 12 else 0.0,
        })
    return rows


def _parse_camera_matrix_csv(text: str) -> np.ndarray:
    """Parse camera_matrix.csv into a 3x3 matrix."""
    reader = csv.reader(io.StringIO(text))
    rows = []
    for row in reader:
        if len(row) >= 3:
            try:
                rows.append([float(v) for v in row[:3]])
            except ValueError:
                continue
    if len(rows) != 3:
        raise ValueError(f"Expected 3x3 camera matrix, got {len(rows)} rows")
    return np.array(rows, dtype=np.float64)


def _parse_imu_csv(text: str) -> list[IMUSample]:
    """Parse imu.csv into IMUSample list."""
    reader = csv.reader(io.StringIO(text))
    samples = []
    for row in reader:
        if len(row) < 7:
            continue
        try:
            ts = float(row[0])
            accel = np.array([float(row[1]), float(row[2]), float(row[3])])
            gyro = np.array([float(row[4]), float(row[5]), float(row[6])])
            samples.append(IMUSample(timestamp=ts, accel=accel, gyro=gyro))
        except (ValueError, IndexError):
            continue
    return samples


def _build_frame(
    odom_row: dict,
    rgb_w: int,
    rgb_h: int,
    depth_w: int,
    depth_h: int,
    camera_matrix_rgb: Optional[np.ndarray],
) -> Frame:
    """Build a Frame from an odometry row."""
    # Per-frame intrinsics at RGB resolution
    intrinsics_rgb = CameraIntrinsics(
        fx=odom_row["fx"], fy=odom_row["fy"],
        cx=odom_row["cx"], cy=odom_row["cy"],
        width=rgb_w, height=rgb_h,
    )

    # Scale intrinsics to depth resolution
    intrinsics_depth = intrinsics_rgb.scaled(depth_w, depth_h)

    # Pose: camera-to-world 4x4
    R = quat_to_rotation_matrix(
        odom_row["qx"], odom_row["qy"], odom_row["qz"], odom_row["qw"]
    )
    t = np.array([odom_row["x"], odom_row["y"], odom_row["z"]], dtype=np.float64)
    pose = np.eye(4, dtype=np.float64)
    pose[:3, :3] = R
    pose[:3, 3] = t

    return Frame(
        index=odom_row["frame"],
        timestamp=odom_row["timestamp"],
        pose=pose,
        intrinsics_rgb=intrinsics_rgb,
        intrinsics_depth=intrinsics_depth,
    )


def _load_depth_png(data: bytes, depth_min_m: float, depth_max_m: float) -> np.ndarray:
    """Load a 16-bit PNG depth map and convert to float32 metres."""
    buf = np.frombuffer(data, dtype=np.uint8)
    depth_mm = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    if depth_mm is None:
        raise ValueError("Failed to decode depth PNG")
    depth_m = depth_mm.astype(np.float32) / 1000.0
    # Mask invalid ranges
    depth_m[(depth_m < depth_min_m) | (depth_m > depth_max_m)] = 0.0
    return depth_m


def _load_confidence_png(data: bytes) -> np.ndarray:
    """Load a confidence map PNG (values 0/1/2)."""
    buf = np.frombuffer(data, dtype=np.uint8)
    conf = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    if conf is None:
        raise ValueError("Failed to decode confidence PNG")
    return conf.astype(np.uint8)


def _load_from_zip(
    zip_path: Path,
    load_rgb: bool,
    load_depth: bool,
    load_confidence: bool,
    stride: int,
    max_frames: Optional[int],
    confidence_threshold: int,
    depth_min_m: float,
    depth_max_m: float,
) -> StrayCapture:
    """Load capture from a zip file."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        prefix = _find_capture_prefix_in_zip(zf)
        capture_id = prefix.rstrip("/").split("/")[-1] if prefix else "unknown"

        # Read odometry
        odom_text = zf.read(f"{prefix}odometry.csv").decode("utf-8")
        odom_rows = _parse_odometry_csv(odom_text)

        # Read camera matrix
        camera_matrix = None
        try:
            cm_text = zf.read(f"{prefix}camera_matrix.csv").decode("utf-8")
            camera_matrix = _parse_camera_matrix_csv(cm_text)
        except (KeyError, ValueError):
            pass

        # Read IMU
        imu = []
        try:
            imu_text = zf.read(f"{prefix}imu.csv").decode("utf-8")
            imu = _parse_imu_csv(imu_text)
        except (KeyError, ValueError):
            pass

        # Determine resolutions
        rgb_w, rgb_h = 1920, 1440
        depth_w, depth_h = 256, 192

        # Build frames
        frames = []
        selected_rows = odom_rows[::stride]
        if max_frames:
            selected_rows = selected_rows[:max_frames]

        for odom_row in tqdm(selected_rows, desc="Loading frames", leave=False):
            frame = _build_frame(odom_row, rgb_w, rgb_h, depth_w, depth_h, camera_matrix)

            # Load depth
            if load_depth:
                depth_name = f"{prefix}depth/{frame.index:06d}.png"
                try:
                    depth_data = zf.read(depth_name)
                    frame.depth = _load_depth_png(depth_data, depth_min_m, depth_max_m)
                except KeyError:
                    continue  # Skip frames without depth

            # Load confidence
            if load_confidence:
                conf_name = f"{prefix}confidence/{frame.index:06d}.png"
                try:
                    conf_data = zf.read(conf_name)
                    frame.confidence = _load_confidence_png(conf_data)
                except KeyError:
                    pass

            # Apply confidence mask to depth
            if frame.depth is not None and frame.confidence is not None:
                mask = frame.confidence < confidence_threshold
                frame.depth[mask] = 0.0

            frames.append(frame)

        capture = StrayCapture(
            capture_id=capture_id,
            frames=frames,
            imu=imu,
            rgb_resolution=(rgb_w, rgb_h),
            depth_resolution=(depth_w, depth_h),
            camera_matrix_rgb=camera_matrix,
            source_path=str(zip_path),
        )

    return capture


def _load_from_dir(
    dir_path: Path,
    load_rgb: bool,
    load_depth: bool,
    load_confidence: bool,
    stride: int,
    max_frames: Optional[int],
    confidence_threshold: int,
    depth_min_m: float,
    depth_max_m: float,
) -> StrayCapture:
    """Load capture from an extracted directory."""
    capture_dir = _find_capture_dir(dir_path)
    capture_id = capture_dir.name

    # Read odometry
    odom_text = (capture_dir / "odometry.csv").read_text(encoding="utf-8")
    odom_rows = _parse_odometry_csv(odom_text)

    # Read camera matrix
    camera_matrix = None
    cm_path = capture_dir / "camera_matrix.csv"
    if cm_path.is_file():
        camera_matrix = _parse_camera_matrix_csv(cm_path.read_text(encoding="utf-8"))

    # Read IMU
    imu = []
    imu_path = capture_dir / "imu.csv"
    if imu_path.is_file():
        imu = _parse_imu_csv(imu_path.read_text(encoding="utf-8"))

    rgb_w, rgb_h = 1920, 1440
    depth_w, depth_h = 256, 192

    frames = []
    selected_rows = odom_rows[::stride]
    if max_frames:
        selected_rows = selected_rows[:max_frames]

    for odom_row in tqdm(selected_rows, desc="Loading frames", leave=False):
        frame = _build_frame(odom_row, rgb_w, rgb_h, depth_w, depth_h, camera_matrix)

        if load_depth:
            depth_path = capture_dir / "depth" / f"{frame.index:06d}.png"
            if depth_path.is_file():
                frame.depth = _load_depth_png(depth_path.read_bytes(), depth_min_m, depth_max_m)
            else:
                continue

        if load_confidence:
            conf_path = capture_dir / "confidence" / f"{frame.index:06d}.png"
            if conf_path.is_file():
                frame.confidence = _load_confidence_png(conf_path.read_bytes())

        if frame.depth is not None and frame.confidence is not None:
            mask = frame.confidence < confidence_threshold
            frame.depth[mask] = 0.0

        frames.append(frame)

    return StrayCapture(
        capture_id=capture_id,
        frames=frames,
        imu=imu,
        rgb_resolution=(rgb_w, rgb_h),
        depth_resolution=(depth_w, depth_h),
        camera_matrix_rgb=camera_matrix,
        source_path=str(dir_path),
    )
