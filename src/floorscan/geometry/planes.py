"""
Plane fitting for floor, ceiling, and wall surfaces.

Floor/ceiling: robust 1D histogram of heights along gravity axis.
Walls: RANSAC on vertical planes in the Manhattan-rotated frame.

Key design decisions:
- Floor height = robust mode of the height histogram (tolerant to furniture).
- Ceiling: declared "not observed" if insufficient evidence.
- Wall lengths = distance between adjacent-plane intersection lines (not boundary points).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.optimize import least_squares

from floorscan.geometry.gravity import SceneEvidence
from floorscan.schema import (
    Measurement, NotObserved, Tier, ConfidenceLevel, Wall, Point2D,
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FittedPlane:
    """A fitted plane: normal . x = d."""
    normal: np.ndarray   # (3,) unit normal
    d: float             # signed distance from origin
    inlier_count: int = 0
    inlier_fraction: float = 0.0
    residual_std: float = 0.0
    label: str = ""      # "floor", "ceiling", "wall_0", etc.

    def distance_to_points(self, points: np.ndarray) -> np.ndarray:
        """Signed distance from points to this plane."""
        return points @ self.normal - self.d

    @property
    def height(self) -> float:
        """Height along gravity (y-component of d for y-up, if normal is [0,1,0])."""
        return self.d


@dataclass
class FloorCeilingResult:
    """Result of floor/ceiling plane fitting."""
    floor_plane: FittedPlane
    floor_height: float
    ceiling_plane: Optional[FittedPlane] = None
    ceiling_height_value: Optional[float] = None
    ceiling_observed: bool = False
    ceiling_evidence: str = ""  # diagnostic info

    @property
    def room_height(self) -> Optional[float]:
        """Floor-to-ceiling distance, if ceiling observed."""
        if self.ceiling_height_value is not None and self.ceiling_observed:
            return abs(self.ceiling_height_value - self.floor_height)
        return None


@dataclass
class WallPlane:
    """A fitted wall plane with its horizontal extent."""
    plane: FittedPlane
    # 2D line in floor plan (start, end) in world x-z
    start_2d: np.ndarray  # (2,)
    end_2d: np.ndarray    # (2,)
    length: float = 0.0
    wall_id: str = ""
    angle: float = 0.0  # angle in radians from Manhattan x-axis


@dataclass
class WallFitResult:
    """Result of wall plane fitting."""
    walls: list[WallPlane] = field(default_factory=list)
    manhattan_yaw: float = 0.0
    is_manhattan: bool = True


# ---------------------------------------------------------------------------
# Floor / ceiling fitting
# ---------------------------------------------------------------------------

def fit_floor_ceiling_planes(
    scene: SceneEvidence,
    bin_width: float = 0.01,
    floor_band: float = 0.05,
    ceiling_min_points: int = 500,
    ceiling_min_fraction: float = 0.005,
    ceiling_min_height_above_floor: float = 2.1,  # Minimum plausible ceiling height (m)
    ceiling_max_height_above_floor: float = 5.0,
) -> FloorCeilingResult:
    """
    Fit floor and ceiling planes from height histogram.

    The floor is the dominant mode of the y-coordinate histogram (y-up world).
    The ceiling is a secondary mode above the floor, if sufficient evidence exists.

    Args:
        scene: SceneEvidence with gravity-aligned point cloud.
        bin_width: Histogram bin width in metres.
        floor_band: Band around floor mode for inlier selection (metres).
        ceiling_min_points: Minimum points to declare ceiling observed.
        ceiling_min_fraction: Minimum fraction of total points for ceiling.
        ceiling_min_height_above_floor: Min plausible ceiling height (m).
        ceiling_max_height_above_floor: Max plausible ceiling height (m).

    Returns:
        FloorCeilingResult with fitted planes and observation status.
    """
    points = scene.points
    heights = points[:, 1]  # y-axis in y-up world

    # --- Floor ---
    h_min, h_max = np.percentile(heights, [1, 99])
    bins = np.arange(h_min, h_max + bin_width, bin_width)
    counts, edges = np.histogram(heights, bins=bins)

    floor_bin_idx = np.argmax(counts)
    floor_height = (edges[floor_bin_idx] + edges[floor_bin_idx + 1]) / 2.0

    # Refine floor with least-squares on inliers
    floor_mask = np.abs(heights - floor_height) < floor_band
    floor_inliers = points[floor_mask]

    if len(floor_inliers) > 10:
        # Fit a plane to the floor inliers
        # For a horizontal floor: normal = [0, 1, 0], d = mean(y)
        floor_h_refined = np.median(floor_inliers[:, 1])
        residuals = floor_inliers[:, 1] - floor_h_refined
        floor_plane = FittedPlane(
            normal=np.array([0, 1, 0], dtype=np.float64),
            d=floor_h_refined,
            inlier_count=len(floor_inliers),
            inlier_fraction=len(floor_inliers) / len(points),
            residual_std=float(np.std(residuals)),
            label="floor",
        )
    else:
        floor_plane = FittedPlane(
            normal=np.array([0, 1, 0], dtype=np.float64),
            d=floor_height,
            inlier_count=int(counts[floor_bin_idx]),
            label="floor",
        )

    # --- Ceiling ---
    # Look for a peak above the floor in the plausible range
    ceil_range_low = floor_height + ceiling_min_height_above_floor
    ceil_range_high = floor_height + ceiling_max_height_above_floor

    ceil_mask = (heights >= ceil_range_low) & (heights <= ceil_range_high)
    ceil_heights = heights[ceil_mask]

    ceiling_plane = None
    ceiling_height_value = None
    ceiling_observed = False
    ceiling_evidence = ""

    if len(ceil_heights) >= ceiling_min_points:
        ceil_fraction = len(ceil_heights) / len(points)
        if ceil_fraction >= ceiling_min_fraction or len(ceil_heights) >= 2000:
            # Find the mode in the ceiling range
            ceil_bins = np.arange(ceil_range_low, ceil_range_high + bin_width, bin_width)
            ceil_counts, ceil_edges = np.histogram(ceil_heights, bins=ceil_bins)

            if len(ceil_counts) > 0 and np.max(ceil_counts) >= ceiling_min_points // 2:
                ceil_peak_idx = np.argmax(ceil_counts)
                ceil_h = (ceil_edges[ceil_peak_idx] + ceil_edges[ceil_peak_idx + 1]) / 2.0

                # Refine
                ceil_inlier_mask = np.abs(heights - ceil_h) < floor_band
                ceil_inliers = points[ceil_inlier_mask]

                if len(ceil_inliers) >= ceiling_min_points:
                    ceil_h_refined = np.median(ceil_inliers[:, 1])
                    residuals = ceil_inliers[:, 1] - ceil_h_refined
                    ceiling_plane = FittedPlane(
                        normal=np.array([0, 1, 0], dtype=np.float64),
                        d=ceil_h_refined,
                        inlier_count=len(ceil_inliers),
                        inlier_fraction=len(ceil_inliers) / len(points),
                        residual_std=float(np.std(residuals)),
                        label="ceiling",
                    )
                    ceiling_height_value = ceil_h_refined
                    ceiling_observed = True
                    ceiling_evidence = (
                        f"Ceiling plane at y={ceil_h_refined:.4f}m, "
                        f"{len(ceil_inliers)} inliers ({ceil_fraction:.4f} of total)"
                    )
                else:
                    ceiling_evidence = (
                        f"Found {len(ceil_inliers)} points near ceiling candidate at "
                        f"y={ceil_h:.4f}m, below threshold of {ceiling_min_points}"
                    )
            else:
                ceiling_evidence = (
                    f"Ceiling range [{ceil_range_low:.2f}, {ceil_range_high:.2f}]m has "
                    f"{len(ceil_heights)} points but no strong peak"
                )
        else:
            ceiling_evidence = (
                f"Only {len(ceil_heights)} points ({len(ceil_heights)/len(points):.6f} fraction) "
                f"in ceiling range, below {ceiling_min_fraction}"
            )
    else:
        ceiling_evidence = (
            f"Only {len(ceil_heights)} points in ceiling range "
            f"[{ceil_range_low:.2f}, {ceil_range_high:.2f}]m, "
            f"below minimum {ceiling_min_points}"
        )

    return FloorCeilingResult(
        floor_plane=floor_plane,
        floor_height=float(floor_plane.d),
        ceiling_plane=ceiling_plane,
        ceiling_height_value=ceiling_height_value,
        ceiling_observed=ceiling_observed,
        ceiling_evidence=ceiling_evidence,
    )


# ---------------------------------------------------------------------------
# Wall fitting
# ---------------------------------------------------------------------------

def fit_wall_planes(
    scene: SceneEvidence,
    floor_ceiling: FloorCeilingResult,
    wall_height_band: tuple[float, float] = (0.3, 0.9),
    ransac_threshold: float = 0.02,
    ransac_iterations: int = 1000,
    min_wall_points: int = 200,
    min_wall_length: float = 0.3,
    seed: int = 42,
) -> WallFitResult:
    """
    Fit vertical wall planes using deterministic RANSAC in the Manhattan-rotated frame.

    Process:
    1. Select points in the wall height band (above floor, below ceiling/furniture).
    2. Rotate to Manhattan-aligned frame.
    3. RANSAC for planes aligned with x or z axis.
    4. Cluster into distinct walls.
    5. Compute wall extents from intersection lines.

    Args:
        scene: SceneEvidence.
        floor_ceiling: Result of floor/ceiling fitting.
        wall_height_band: (min_frac, max_frac) of room height for wall points.
        ransac_threshold: RANSAC inlier threshold (metres).
        ransac_iterations: Number of RANSAC iterations.
        min_wall_points: Minimum inlier count for a valid wall.
        min_wall_length: Minimum wall length (metres).
        seed: Random seed.

    Returns:
        WallFitResult with fitted wall planes.
    """
    rng = np.random.RandomState(seed)
    points = scene.points

    # Determine wall height range
    floor_h = floor_ceiling.floor_height
    if floor_ceiling.ceiling_observed and floor_ceiling.ceiling_height_value is not None:
        room_height = floor_ceiling.ceiling_height_value - floor_h
    else:
        room_height = 2.5  # assume 2.5m if ceiling not observed

    wall_y_min = floor_h + wall_height_band[0] * room_height
    wall_y_max = floor_h + wall_height_band[1] * room_height

    # Select points in wall band
    y = points[:, 1]
    wall_mask = (y >= wall_y_min) & (y <= wall_y_max)
    wall_points = points[wall_mask]

    if len(wall_points) < min_wall_points:
        return WallFitResult(manhattan_yaw=scene.manhattan_yaw)

    # Rotate to Manhattan-aligned frame (rotate around y by -manhattan_yaw)
    yaw = scene.manhattan_yaw
    cos_y, sin_y = np.cos(-yaw), np.sin(-yaw)
    R_manhattan = np.array([
        [cos_y, 0, sin_y],
        [0, 1, 0],
        [-sin_y, 0, cos_y],
    ])
    wall_pts_rot = (R_manhattan @ wall_points.T).T

    # Project to x-z plane
    xz = wall_pts_rot[:, [0, 2]]

    # Find walls aligned with x-axis (constant z) and z-axis (constant x)
    walls = []
    remaining_mask = np.ones(len(wall_pts_rot), dtype=bool)

    for axis_idx, axis_name in [(0, "x"), (2, "z")]:
        # Histogram along the perpendicular axis to find wall candidates
        coords = wall_pts_rot[:, axis_idx]
        perp_axis = 2 if axis_idx == 0 else 0

        h_min, h_max = np.percentile(coords[remaining_mask], [2, 98])
        bins = np.arange(h_min, h_max + 0.02, 0.02)  # 2cm bins
        counts, edges = np.histogram(coords[remaining_mask], bins=bins)

        # Find peaks (bins with more than min_wall_points)
        threshold = max(min_wall_points, np.percentile(counts[counts > 0], 75))
        peak_indices = np.where(counts >= threshold)[0]

        # Cluster adjacent peak bins
        clusters = []
        if len(peak_indices) > 0:
            current_cluster = [peak_indices[0]]
            for i in range(1, len(peak_indices)):
                if peak_indices[i] - peak_indices[i - 1] <= 2:
                    current_cluster.append(peak_indices[i])
                else:
                    clusters.append(current_cluster)
                    current_cluster = [peak_indices[i]]
            clusters.append(current_cluster)

        for cluster in clusters:
            cluster_centers = [(edges[i] + edges[i + 1]) / 2.0 for i in cluster]
            wall_coord = np.mean(cluster_centers)

            # Select inliers
            inlier_mask = (
                remaining_mask &
                (np.abs(wall_pts_rot[:, axis_idx] - wall_coord) < ransac_threshold * 2)
            )
            inlier_pts = wall_pts_rot[inlier_mask]

            if len(inlier_pts) < min_wall_points:
                continue

            # Refine wall position
            wall_coord_refined = np.median(inlier_pts[:, axis_idx])
            residuals = inlier_pts[:, axis_idx] - wall_coord_refined

            # Wall extent along the parallel axis
            parallel_coords = inlier_pts[:, perp_axis]
            extent_min = np.percentile(parallel_coords, 2)
            extent_max = np.percentile(parallel_coords, 98)
            wall_length = extent_max - extent_min

            if wall_length < min_wall_length:
                continue

            # Build normal in Manhattan-rotated frame
            normal_rot = np.zeros(3)
            normal_rot[axis_idx] = 1.0

            # Transform back to world frame
            R_inv = R_manhattan.T
            normal_world = R_inv @ normal_rot

            # Wall endpoints in world x-z
            if axis_idx == 0:
                # wall is constant-x -> extends along z
                start_rot = np.array([wall_coord_refined, 0, extent_min])
                end_rot = np.array([wall_coord_refined, 0, extent_max])
            else:
                # wall is constant-z -> extends along x
                start_rot = np.array([extent_min, 0, wall_coord_refined])
                end_rot = np.array([extent_max, 0, wall_coord_refined])

            start_world = R_inv @ start_rot
            end_world = R_inv @ end_rot

            plane = FittedPlane(
                normal=normal_world,
                d=float(np.dot(normal_world, R_inv @ np.array([wall_coord_refined, 0, 0])
                               if axis_idx == 0
                               else R_inv @ np.array([0, 0, wall_coord_refined]))),
                inlier_count=len(inlier_pts),
                inlier_fraction=len(inlier_pts) / len(wall_points),
                residual_std=float(np.std(residuals)),
                label=f"wall_{len(walls)}",
            )

            wall = WallPlane(
                plane=plane,
                start_2d=start_world[[0, 2]],
                end_2d=end_world[[0, 2]],
                length=wall_length,
                wall_id=f"wall_{len(walls)}",
                angle=yaw if axis_idx == 2 else yaw + np.pi / 2,
            )
            walls.append(wall)

            # Remove inliers
            remaining_mask &= ~inlier_mask

    return WallFitResult(
        walls=walls,
        manhattan_yaw=yaw,
        is_manhattan=True,
    )
