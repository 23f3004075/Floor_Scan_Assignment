"""
Room layout extraction from fitted planes.

Converts wall planes into a room polygon (floor plan), computes floor area,
perimeter, and packages as schema-compliant RoomPlan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union

from floorscan.geometry.gravity import SceneEvidence
from floorscan.geometry.planes import FloorCeilingResult, WallFitResult, WallPlane
from floorscan.schema import (
    Measurement, NotObserved, Tier, ConfidenceLevel,
    RoomPlan, Wall, Point2D, Opening,
)


@dataclass
class LayoutResult:
    """Intermediate layout result before quality gates."""
    room_polygon: Optional[Polygon] = None
    walls: list[Wall] = field(default_factory=list)
    floor_area: float = 0.0
    perimeter: float = 0.0
    floor_height: float = 0.0
    ceiling_height: Optional[float] = None
    ceiling_observed: bool = False
    ceiling_evidence: str = ""
    wall_planes: list[WallPlane] = field(default_factory=list)


def _intersect_wall_lines(
    walls: list[WallPlane],
) -> list[np.ndarray]:
    """
    Find room corners by intersecting adjacent wall lines.

    Returns ordered corner points in 2D (x, z) world coordinates.
    """
    if len(walls) < 3:
        # Not enough walls for a closed polygon; use wall endpoints
        corners = []
        for w in walls:
            corners.append(w.start_2d)
            corners.append(w.end_2d)
        return corners

    # Sort walls by angle to get adjacency ordering
    sorted_walls = sorted(walls, key=lambda w: w.angle % (2 * np.pi))

    corners = []
    n = len(sorted_walls)
    for i in range(n):
        w1 = sorted_walls[i]
        w2 = sorted_walls[(i + 1) % n]

        # Intersect the infinite lines of these two walls
        corner = _line_line_intersection_2d(
            w1.start_2d, w1.end_2d,
            w2.start_2d, w2.end_2d,
        )
        if corner is not None:
            corners.append(corner)

    return corners


def _line_line_intersection_2d(
    p1: np.ndarray, p2: np.ndarray,
    p3: np.ndarray, p4: np.ndarray,
) -> Optional[np.ndarray]:
    """
    Find the intersection of two infinite lines defined by (p1, p2) and (p3, p4).

    Returns None if lines are parallel.
    """
    d1 = p2 - p1
    d2 = p4 - p3

    cross = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(cross) < 1e-10:
        return None  # Parallel

    dp = p3 - p1
    t = (dp[0] * d2[1] - dp[1] * d2[0]) / cross

    intersection = p1 + t * d1
    return intersection


def extract_room_layout(
    scene: SceneEvidence,
    floor_ceiling: FloorCeilingResult,
    wall_result: WallFitResult,
    seed: int = 42,
) -> LayoutResult:
    """
    Extract the room layout from fitted planes.

    Process:
    1. Find corners by intersecting adjacent wall planes.
    2. Form a polygon from the corners.
    3. Ensure the polygon is valid (non-self-intersecting, positive area).
    4. Compute floor area and perimeter.
    """
    walls = wall_result.walls

    if len(walls) < 3:
        # Fallback: use convex hull of wall points in x-z plane
        return _fallback_layout(scene, floor_ceiling, walls)

    # Get corners from wall intersections
    corners = _intersect_wall_lines(walls)

    if len(corners) < 3:
        return _fallback_layout(scene, floor_ceiling, walls)

    # Create polygon
    try:
        corner_tuples = [(float(c[0]), float(c[1])) for c in corners]
        polygon = Polygon(corner_tuples)

        if not polygon.is_valid:
            polygon = polygon.buffer(0)  # Fix self-intersections
            if isinstance(polygon, MultiPolygon):
                polygon = max(polygon.geoms, key=lambda g: g.area)

        if polygon.area < 0.5:  # Less than 0.5 m² is suspicious
            return _fallback_layout(scene, floor_ceiling, walls)

    except Exception:
        return _fallback_layout(scene, floor_ceiling, walls)

    # Build schema-compliant walls
    schema_walls = []
    coords = list(polygon.exterior.coords)
    for i in range(len(coords) - 1):
        p_start = coords[i]
        p_end = coords[i + 1]
        length = np.sqrt((p_end[0] - p_start[0])**2 + (p_end[1] - p_start[1])**2)

        if length < 0.1:  # Skip degenerate walls
            continue

        # Simple CI: ±2cm for LiDAR (will be refined by quality gates)
        wall = Wall(
            wall_id=f"wall_{i}",
            start=Point2D(x=p_start[0], y=p_start[1]),
            end=Point2D(x=p_end[0], y=p_end[1]),
            length=Measurement(
                value=length,
                ci_low=length - 0.02,
                ci_high=length + 0.02,
                tier=Tier.LIDAR,
                method="plane_intersection",
            ),
            surface_id=f"surface_wall_{i}",
        )
        schema_walls.append(wall)

    floor_area = polygon.area
    perimeter = polygon.length

    return LayoutResult(
        room_polygon=polygon,
        walls=schema_walls,
        floor_area=floor_area,
        perimeter=perimeter,
        floor_height=floor_ceiling.floor_height,
        ceiling_height=floor_ceiling.room_height,
        ceiling_observed=floor_ceiling.ceiling_observed,
        ceiling_evidence=floor_ceiling.ceiling_evidence,
        wall_planes=walls,
    )


def _fallback_layout(
    scene: SceneEvidence,
    floor_ceiling: FloorCeilingResult,
    walls: list[WallPlane],
) -> LayoutResult:
    """
    Fallback layout when wall intersection fails.
    Uses convex hull of horizontal point projections.
    """
    points = scene.points
    # Select points near floor height
    floor_h = floor_ceiling.floor_height
    floor_mask = np.abs(points[:, 1] - floor_h) < 0.3
    floor_points = points[floor_mask]

    if len(floor_points) < 10:
        return LayoutResult(
            floor_height=floor_h,
            ceiling_height=floor_ceiling.room_height,
            ceiling_observed=floor_ceiling.ceiling_observed,
            ceiling_evidence=floor_ceiling.ceiling_evidence,
        )

    # Convex hull in x-z
    from scipy.spatial import ConvexHull
    xz = floor_points[:, [0, 2]]

    try:
        hull = ConvexHull(xz)
        hull_points = xz[hull.vertices]
        polygon = Polygon([(p[0], p[1]) for p in hull_points])

        # Build walls from hull edges
        schema_walls = []
        coords = list(polygon.exterior.coords)
        for i in range(len(coords) - 1):
            p_start = coords[i]
            p_end = coords[i + 1]
            length = np.sqrt((p_end[0] - p_start[0])**2 + (p_end[1] - p_start[1])**2)
            if length < 0.1:
                continue

            wall = Wall(
                wall_id=f"wall_{i}",
                start=Point2D(x=p_start[0], y=p_start[1]),
                end=Point2D(x=p_end[0], y=p_end[1]),
                length=Measurement(
                    value=length,
                    ci_low=length - 0.05,
                    ci_high=length + 0.05,
                    tier=Tier.LIDAR,
                    method="convex_hull_fallback",
                    flags=["fallback_layout"],
                ),
                surface_id=f"surface_wall_{i}",
            )
            schema_walls.append(wall)

        return LayoutResult(
            room_polygon=polygon,
            walls=schema_walls,
            floor_area=polygon.area,
            perimeter=polygon.length,
            floor_height=floor_h,
            ceiling_height=floor_ceiling.room_height,
            ceiling_observed=floor_ceiling.ceiling_observed,
            ceiling_evidence=floor_ceiling.ceiling_evidence,
            wall_planes=walls,
        )

    except Exception:
        return LayoutResult(
            floor_height=floor_h,
            ceiling_height=floor_ceiling.room_height,
            ceiling_observed=floor_ceiling.ceiling_observed,
            ceiling_evidence=floor_ceiling.ceiling_evidence,
        )
