"""
Synthetic room generator for test-driven development and calibration verification.

Generates parametric rooms (rectangular, L-shaped) with:
- Configurable dimensions (width, length, ceiling height)
- Configurable openings (doors, windows)
- Trajectory generation (perimeter walk, ceiling sweep or floor-only)
- Injected noise, vertical drift, and depth confidence
- Analytical ground truth PropertyPlan for automatic grading & gate verification.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional
import numpy as np

from floorscan.schema import (
    PropertyPlan,
    RoomPlan,
    Wall,
    Opening,
    OpeningType,
    Measurement,
    Point2D,
    ConfidenceLevel,
    Tier,
)


@dataclass
class SyntheticOpening:
    wall_index: int
    offset_along_wall: float
    width: float
    height: float
    sill_height: float = 0.0
    opening_type: OpeningType = OpeningType.DOOR


@dataclass
class SyntheticRoomConfig:
    room_id: str = "synth_room_01"
    name: str = "Living Room"
    width: float = 4.0      # meters along X
    length: float = 5.0     # meters along Y
    height: float = 2.6     # meters ceiling height
    include_ceiling_sweep: bool = True
    vertical_drift_m_per_min: float = 0.0
    depth_noise_std: float = 0.005 # 5mm depth noise
    openings: List[SyntheticOpening] = field(default_factory=lambda: [
        SyntheticOpening(wall_index=0, offset_along_wall=1.5, width=0.90, height=2.05, opening_type=OpeningType.DOOR),
        SyntheticOpening(wall_index=1, offset_along_wall=2.0, width=1.20, height=1.40, sill_height=0.90, opening_type=OpeningType.WINDOW),
    ])


class SyntheticRoom:
    """Analytical geometry and ray-casting camera for synthetic rooms."""

    def __init__(self, config: SyntheticRoomConfig):
        self.cfg = config
        self.w = config.width
        self.l = config.length
        self.h = config.height
        
        # 4 walls in counter-clockwise order around the rectangle:
        # Wall 0: (0,0) -> (w, 0)      [along X, facing -Y]
        # Wall 1: (w,0) -> (w, l)      [along Y, facing +X]
        # Wall 2: (w,l) -> (0, l)      [along -X, facing +Y]
        # Wall 3: (0,l) -> (0, 0)      [along -Y, facing -X]
        self.corners = np.array([
            [0.0, 0.0],
            [self.w, 0.0],
            [self.w, self.l],
            [0.0, self.l],
        ], dtype=np.float64)

    def get_ground_truth_plan(self) -> PropertyPlan:
        """Construct the exact ground-truth PropertyPlan."""
        walls = []
        for i in range(4):
            p1 = self.corners[i]
            p2 = self.corners[(i + 1) % 4]
            length = float(np.linalg.norm(p2 - p1))
            
            wall_openings = []
            for op in self.cfg.openings:
                if op.wall_index == i:
                    wall_openings.append(
                        Opening(
                            opening_id=f"op_{op.opening_type.value}_{i}",
                            wall_id=f"wall_{i}",
                            opening_type=op.opening_type,
                            width=Measurement(
                                value=op.width,
                                ci_low=op.width,
                                ci_high=op.width,
                                confidence_level=ConfidenceLevel.HIGH,
                                method="ground_truth",
                                tier=Tier.LIDAR,
                            ),
                            height=Measurement(
                                value=op.height,
                                ci_low=op.height,
                                ci_high=op.height,
                                confidence_level=ConfidenceLevel.HIGH,
                                method="ground_truth",
                                tier=Tier.LIDAR,
                            ),
                            position_along_wall=op.offset_along_wall + op.width / 2.0,
                        )
                    )

            walls.append(
                Wall(
                    wall_id=f"wall_{i}",
                    start=Point2D(x=float(p1[0]), y=float(p1[1])),
                    end=Point2D(x=float(p2[0]), y=float(p2[1])),
                    length=Measurement(
                        value=length,
                        ci_low=length,
                        ci_high=length,
                        confidence_level=ConfidenceLevel.HIGH,
                        method="ground_truth",
                        tier=Tier.LIDAR,
                    ),
                    surface_id=f"surf_wall_{i}",
                    openings=wall_openings,
                )
            )

        area = self.w * self.l
        perimeter = 2 * (self.w + self.l)
        
        ceiling_meas = Measurement(
            value=self.h,
            ci_low=self.h,
            ci_high=self.h,
            confidence_level=ConfidenceLevel.HIGH,
            method="ground_truth",
            tier=Tier.LIDAR,
        )

        room = RoomPlan(
            room_id=self.cfg.room_id,
            room_name=self.cfg.name,
            floor_polygon=[Point2D(x=float(p[0]), y=float(p[1])) for p in self.corners],
            walls=walls,
            floor_area=Measurement(
                value=area,
                ci_low=area,
                ci_high=area,
                confidence_level=ConfidenceLevel.HIGH,
                method="ground_truth",
                tier=Tier.LIDAR,
            ),
            perimeter=Measurement(
                value=perimeter,
                ci_low=perimeter,
                ci_high=perimeter,
                confidence_level=ConfidenceLevel.HIGH,
                method="ground_truth",
                tier=Tier.LIDAR,
            ),
            ceiling_height=ceiling_meas,
        )

        return PropertyPlan(
            rooms=[room],
            total_floor_area=Measurement(
                value=area,
                ci_low=area,
                ci_high=area,
                confidence_level=ConfidenceLevel.HIGH,
                method="ground_truth",
                tier=Tier.LIDAR,
            ),
            tier=Tier.LIDAR,
        )

    def generate_point_cloud(
        self,
        points_per_wall: int = 1500,
        points_floor: int = 2500,
        points_ceiling: int = 2000,
        rng: Optional[np.random.Generator] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate a synthetic 3D point cloud of the room.
        Returns:
            points: (N, 3) xyz coordinates in world frame (Z-up)
            normals: (N, 3) surface normals
        """
        if rng is None:
            rng = np.random.default_rng(42)

        pts_list = []
        normals_list = []

        # 1. Floor at z = 0 (Normal: [0, 0, 1])
        fx = rng.uniform(0.05, self.w - 0.05, size=points_floor)
        fy = rng.uniform(0.05, self.l - 0.05, size=points_floor)
        fz = rng.normal(0.0, self.cfg.depth_noise_std, size=points_floor)
        pts_list.append(np.column_stack([fx, fy, fz]))
        normals_list.append(np.tile([0.0, 0.0, 1.0], (points_floor, 1)))

        # 2. Ceiling at z = h (Normal: [0, 0, -1]) if sweep included
        if self.cfg.include_ceiling_sweep:
            cx = rng.uniform(0.05, self.w - 0.05, size=points_ceiling)
            cy = rng.uniform(0.05, self.l - 0.05, size=points_ceiling)
            cz = rng.normal(self.h, self.cfg.depth_noise_std, size=points_ceiling)
            pts_list.append(np.column_stack([cx, cy, cz]))
            normals_list.append(np.tile([0.0, 0.0, -1.0], (points_ceiling, 1)))

        # 3. Four walls
        # Wall 0: y=0, x in [0, w], z in [0, h], Normal: [0, 1, 0]
        w0_x = rng.uniform(0.0, self.w, size=points_per_wall)
        w0_y = rng.normal(0.0, self.cfg.depth_noise_std, size=points_per_wall)
        w0_z = rng.uniform(0.0, self.h, size=points_per_wall)
        # Exclude opening regions
        mask0 = np.ones(points_per_wall, dtype=bool)
        for op in self.cfg.openings:
            if op.wall_index == 0:
                in_op = (w0_x >= op.offset_along_wall) & (w0_x <= op.offset_along_wall + op.width) & \
                        (w0_z >= op.sill_height) & (w0_z <= op.sill_height + op.height)
                mask0 &= ~in_op
        pts_list.append(np.column_stack([w0_x[mask0], w0_y[mask0], w0_z[mask0]]))
        normals_list.append(np.tile([0.0, 1.0, 0.0], (np.sum(mask0), 1)))

        # Wall 1: x=w, y in [0, l], z in [0, h], Normal: [-1, 0, 0]
        w1_x = rng.normal(self.w, self.cfg.depth_noise_std, size=points_per_wall)
        w1_y = rng.uniform(0.0, self.l, size=points_per_wall)
        w1_z = rng.uniform(0.0, self.h, size=points_per_wall)
        mask1 = np.ones(points_per_wall, dtype=bool)
        for op in self.cfg.openings:
            if op.wall_index == 1:
                in_op = (w1_y >= op.offset_along_wall) & (w1_y <= op.offset_along_wall + op.width) & \
                        (w1_z >= op.sill_height) & (w1_z <= op.sill_height + op.height)
                mask1 &= ~in_op
        pts_list.append(np.column_stack([w1_x[mask1], w1_y[mask1], w1_z[mask1]]))
        normals_list.append(np.tile([-1.0, 0.0, 0.0], (np.sum(mask1), 1)))

        # Wall 2: y=l, x in [0, w], z in [0, h], Normal: [0, -1, 0]
        w2_x = rng.uniform(0.0, self.w, size=points_per_wall)
        w2_y = rng.normal(self.l, self.cfg.depth_noise_std, size=points_per_wall)
        w2_z = rng.uniform(0.0, self.h, size=points_per_wall)
        pts_list.append(np.column_stack([w2_x, w2_y, w2_z]))
        normals_list.append(np.tile([0.0, -1.0, 0.0], (points_per_wall, 1)))

        # Wall 3: x=0, y in [0, l], z in [0, h], Normal: [1, 0, 0]
        w3_x = rng.normal(0.0, self.cfg.depth_noise_std, size=points_per_wall)
        w3_y = rng.uniform(0.0, self.l, size=points_per_wall)
        w3_z = rng.uniform(0.0, self.h, size=points_per_wall)
        pts_list.append(np.column_stack([w3_x, w3_y, w3_z]))
        normals_list.append(np.tile([1.0, 0.0, 0.0], (points_per_wall, 1)))

        points = np.vstack(pts_list)
        normals = np.vstack(normals_list)
        return points, normals
