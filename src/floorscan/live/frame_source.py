"""
Unified FrameSource abstraction.

Implements the core architecture rule from agent_prompt.md:
"Introduce a FrameSource abstraction (iterator of timestamped frames carrying rgb,
optional depth, confidence, pose, intrinsics, imu, plus provenance).
Batch processing is a replay of a live stream."
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator, Optional, List, Dict, Any
import numpy as np

from floorscan.io.stray_scanner import Frame, CameraIntrinsics, StrayCapture, load_stray_capture


class FrameSource(ABC):
    """Abstract iterator of timestamped frames."""

    @abstractmethod
    def __iter__(self) -> Iterator[Frame]:
        """Yield frames sequentially."""
        pass

    @property
    @abstractmethod
    def total_frames(self) -> Optional[int]:
        """Total frame count if known ahead of time."""
        pass

    @property
    def is_live(self) -> bool:
        """True if receiving live data, False for batch/replay."""
        return False

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Capture metadata (capture_id, source type, etc.)."""
        pass


class StrayScannerSource(FrameSource):
    """Batch FrameSource reading from a Stray Scanner directory or zip."""

    def __init__(self, path: Path | str, max_frames: Optional[int] = None):
        self.path = Path(path)
        self.max_frames = max_frames
        self.capture: Optional[StrayCapture] = None

    def _ensure_loaded(self) -> StrayCapture:
        if self.capture is None:
            self.capture = load_stray_capture(self.path, max_frames=self.max_frames)
        return self.capture

    def __iter__(self) -> Iterator[Frame]:
        capture = self._ensure_loaded()
        for f in capture.frames:
            yield f

    @property
    def total_frames(self) -> int:
        return len(self._ensure_loaded().frames)

    def get_metadata(self) -> Dict[str, Any]:
        capture = self._ensure_loaded()
        return {
            "capture_id": capture.capture_id,
            "source_type": "stray_scanner",
            "path": str(self.path),
            "num_frames": len(capture.frames),
        }


class ReplayLiveSource(FrameSource):
    """
    Simulates a live streaming sensor by replaying a batch capture with simulated clock delays.
    Enables reproducible live pipeline and latency testing.
    """

    def __init__(self, inner_source: FrameSource, playback_rate: float = 1.0):
        self.inner = inner_source
        self.playback_rate = playback_rate

    @property
    def is_live(self) -> bool:
        return True

    @property
    def total_frames(self) -> Optional[int]:
        return self.inner.total_frames

    def get_metadata(self) -> Dict[str, Any]:
        meta = self.inner.get_metadata()
        meta["mode"] = "replay_live"
        meta["playback_rate"] = self.playback_rate
        return meta

    def __iter__(self) -> Iterator[Frame]:
        frames = list(self.inner)
        if not frames:
            return

        t_prev = frames[0].timestamp
        for f in frames:
            dt = (f.timestamp - t_prev) / max(0.1, self.playback_rate)
            if 0 < dt < 0.2:
                time.sleep(dt)
            t_prev = f.timestamp
            yield f
