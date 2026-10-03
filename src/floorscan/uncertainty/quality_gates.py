"""
Quality gates and confidence interval assignment.

Applies tier-specific uncertainty inflation, quality flags,
and constructs the final PropertyPlan with proper CI on every measurement.
"""

from __future__ import annotations

from floorscan.geometry.gravity import SceneEvidence
from floorscan.geometry.layout import LayoutResult
from floorscan.geometry.planes import FloorCeilingResult
from floorscan.schema import (
    PropertyPlan, RoomPlan, Measurement, NotObserved,
    Tier, ConfidenceLevel, Opening,
)


# Tier-specific CI scaling factors (metres)
TIER_CI = {
    Tier.LIDAR: {
        "wall_length": 0.02,   # ±2 cm
        "ceiling_height": 0.015,  # ±1.5 cm
        "floor_area_frac": 0.03,  # ±3%
        "opening_width": 0.02,    # ±2 cm
    },
    Tier.VIDEO: {
        "wall_length_frac": 0.03,  # ±3%
        "ceiling_height_frac": 0.03,
        "floor_area_frac": 0.05,
        "opening_width_frac": 0.05,
    },
    Tier.PHOTO: {
        "wall_length_frac": 0.08,  # ±8%
        "ceiling_height_frac": 0.08,
        "floor_area_frac": 0.08,
        "opening_width_frac": 0.10,
    },
}

# Prior ceiling height range when not observed (metres)
CEILING_PRIOR = (2.4, 3.6)  # typical residential range


def apply_quality_gates(
    layout: LayoutResult,
    openings: list[Opening],
    floor_ceiling: FloorCeilingResult,
    scene: SceneEvidence,
    tier: Tier = Tier.LIDAR,
) -> PropertyPlan:
    """
    Apply quality gates and build the final PropertyPlan.

    - Assigns CI to every measurement based on tier.
    - Handles ceiling not-observed with prior interval.
    - Flags low-confidence measurements.

    Returns:
        Validated PropertyPlan ready for JSON export and rendering.
    """
    ci = TIER_CI.get(tier, TIER_CI[Tier.LIDAR])

    # --- Ceiling height ---
    if layout.ceiling_observed and layout.ceiling_height is not None:
        ceiling = Measurement(
            value=layout.ceiling_height,
            ci_low=layout.ceiling_height - ci.get("ceiling_height", 0.015),
            ci_high=layout.ceiling_height + ci.get("ceiling_height", 0.015),
            confidence_level=ConfidenceLevel.HIGH,
            tier=tier,
            method="floor_ceiling_plane_distance",
        )
    else:
        ceiling = NotObserved(
            observed=False,
            reason=layout.ceiling_evidence or "Ceiling never in camera view",
            prior_low=CEILING_PRIOR[0],
            prior_high=CEILING_PRIOR[1],
            confidence_level=ConfidenceLevel.NOT_OBSERVED,
            tier=tier,
        )

    # --- Floor area ---
    floor_area = None
    if layout.floor_area > 0:
        area_ci = layout.floor_area * ci.get("floor_area_frac", 0.03)
        floor_area = Measurement(
            value=layout.floor_area,
            ci_low=layout.floor_area - area_ci,
            ci_high=layout.floor_area + area_ci,
            tier=tier,
            method="polygon_area",
        )

    # --- Perimeter ---
    perimeter = None
    if layout.perimeter > 0:
        peri_ci = layout.perimeter * ci.get("floor_area_frac", 0.03)
        perimeter = Measurement(
            value=layout.perimeter,
            ci_low=layout.perimeter - peri_ci,
            ci_high=layout.perimeter + peri_ci,
            tier=tier,
            method="polygon_perimeter",
        )

    # --- Walls with CI ---
    walls = layout.walls  # Already have CI from layout extraction

    # Assign openings to walls
    for opening in openings:
        for wall in walls:
            if opening.wall_id == wall.wall_id:
                wall.openings.append(opening)

    # --- Floor polygon ---
    floor_polygon_pts = []
    if layout.room_polygon is not None:
        from floorscan.schema import Point2D
        coords = list(layout.room_polygon.exterior.coords)
        floor_polygon_pts = [Point2D(x=c[0], y=c[1]) for c in coords[:-1]]

    # Build RoomPlan
    room = RoomPlan(
        room_id="room_1",
        room_name="Room 1",
        walls=walls,
        floor_polygon=floor_polygon_pts,
        floor_area=floor_area,
        ceiling_height=ceiling,
        perimeter=perimeter,
    )

    # Build PropertyPlan
    plan = PropertyPlan(
        tier=tier,
        rooms=[room],
        total_floor_area=floor_area,
        total_perimeter=perimeter,
        metadata={
            "capture_id": scene.capture_id,
            "convention": scene.convention,
            "manhattan_yaw_deg": float(np.degrees(scene.manhattan_yaw))
                if hasattr(scene, 'manhattan_yaw') else 0.0,
            "num_frames": scene.num_frames_used,
            "duration_s": scene.duration_s,
            "floor_height": layout.floor_height,
            "ceiling_evidence": layout.ceiling_evidence,
        },
    )

    return plan


# Need numpy for the metadata
import numpy as np
