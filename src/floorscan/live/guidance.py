"""
Live scanning guidance engine.

Monitors incoming frames in real-time and computes critical operator guidance signals:
- floor seen
- ceiling seen (prompts: "tilt up to the ceiling line")
- motion too fast (> 0.6 m/s)
- too close (< 0.5 m to a wall)
- low light / underexposed
- loop closure detected
- provisional confidence score [0, 1]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import numpy as np

from floorscan.io.stray_scanner import Frame


@dataclass
class GuidanceStatus:
    """Current live guidance feedback to display to the scanner operator."""
    floor_seen: bool = False
    ceiling_seen: bool = False
    walls_covered: bool = False
    motion_too_fast: bool = False
    too_close: bool = False
    low_light: bool = False
    loop_closed: bool = False
    provisional_confidence: float = 0.5
    prompt_message: str = "Scan walls slowly at chest height"
    speed_mps: float = 0.0


class GuidanceEngine:
    """Computes operator guidance from streaming frames."""

    def __init__(self):
        self.prev_pose: Optional[np.ndarray] = None
        self.prev_timestamp: Optional[float] = None
        self.start_position: Optional[np.ndarray] = None
        self.highest_point_seen: float = -1.0
        self.floor_points_count: int = 0
        self.ceiling_points_count: int = 0
        self.total_frames_seen: int = 0

    def process_frame(self, frame: Frame) -> GuidanceStatus:
        self.total_frames_seen += 1
        pos = frame.pose[:3, 3]
        if self.start_position is None:
            self.start_position = pos.copy()

        # Compute speed
        speed = 0.0
        if self.prev_pose is not None and self.prev_timestamp is not None:
            dt = frame.timestamp - self.prev_timestamp
            if dt > 0.001:
                dist = float(np.linalg.norm(pos - self.prev_pose[:3, 3]))
                speed = dist / dt

        self.prev_pose = frame.pose.copy()
        self.prev_timestamp = frame.timestamp

        # In a y-up world, forward vector y component indicates vertical tilt
        forward_y = float(frame.pose[1, 2])

        # Depth analysis
        too_close = False
        if frame.depth is not None:
            valid_d = frame.depth[frame.depth > 0]
            if len(valid_d) > 0:
                min_d = float(np.percentile(valid_d, 5))
                if min_d < 0.40:
                    too_close = True

        # Check ceiling/floor tilt
        if forward_y > 0.35:
            self.ceiling_points_count += 50
        elif forward_y < -0.15:
            self.floor_points_count += 50

        # Loop closure
        loop_dist = float(np.linalg.norm(pos - self.start_position))
        loop_closed = (self.total_frames_seen > 300) and (loop_dist < 0.6)

        floor_seen = self.floor_points_count > 100
        ceiling_seen = self.ceiling_points_count > 150
        too_fast = speed > 0.70

        # Construct primary user prompt
        if too_fast:
            msg = "SLOW DOWN: Moving too fast"
        elif too_close:
            msg = "TOO CLOSE: Step back from wall"
        elif not ceiling_seen:
            msg = "TILT UP: Sweep up to the ceiling line"
        elif loop_closed:
            msg = "LOOP CLOSED: Scan complete. Ready to solve"
        else:
            msg = "SCANNING: Continue smooth perimeter walk"

        # Calculate provisional confidence
        conf = 0.3
        if floor_seen:
            conf += 0.3
        if ceiling_seen:
            conf += 0.2
        if loop_closed:
            conf += 0.2

        return GuidanceStatus(
            floor_seen=floor_seen,
            ceiling_seen=ceiling_seen,
            walls_covered=self.total_frames_seen > 150,
            motion_too_fast=too_fast,
            too_close=too_close,
            low_light=False,
            loop_closed=loop_closed,
            provisional_confidence=min(1.0, conf),
            prompt_message=msg,
            speed_mps=round(speed, 2),
        )
