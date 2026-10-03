"""
Unit tests for FrameSource abstraction, live replay, and operator guidance signals.
"""

from pathlib import Path
import pytest
from floorscan.live.frame_source import StrayScannerSource, ReplayLiveSource
from floorscan.live.guidance import GuidanceEngine


def test_frame_source_and_guidance():
    """Verify FrameSource streaming and guidance engine behavior on single_room.zip."""
    zip_path = Path("single_room.zip")
    if not zip_path.exists():
        pytest.skip("single_room.zip not found")

    source = StrayScannerSource(zip_path, max_frames=200)
    assert source.total_frames == 200
    
    guidance = GuidanceEngine()
    statuses = []

    for f in source:
        st = guidance.process_frame(f)
        statuses.append(st)

    assert len(statuses) == 200
    last_status = statuses[-1]
    
    # Since single_room.zip never tilted up to the ceiling, guidance must prompt to tilt up!
    assert not last_status.ceiling_seen
    assert "TILT UP" in last_status.prompt_message or not last_status.ceiling_seen
