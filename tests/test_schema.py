"""
Unit tests for schema validation, serialization, and synthetic room generator.
"""

import json
import pytest
from floorscan.schema import PropertyPlan, RoomPlan, Wall, Opening, OpeningType, Measurement, ConfidenceLevel, Tier
from tests.synth.generator import SyntheticRoom, SyntheticRoomConfig


def test_schema_serialization():
    """Ensure PropertyPlan validates, serializes to JSON, and re-parses cleanly."""
    cfg = SyntheticRoomConfig(width=3.5, length=4.2, height=2.7)
    synth = SyntheticRoom(cfg)
    gt_plan = synth.get_ground_truth_plan()
    
    # Export to dict and JSON string
    data_dict = gt_plan.model_dump()
    json_str = gt_plan.model_dump_json()
    
    # Re-parse
    reloaded = PropertyPlan.model_validate_json(json_str)
    assert len(reloaded.rooms) == 1
    assert reloaded.rooms[0].room_name == "Living Room"
    assert reloaded.rooms[0].floor_area.value == pytest.approx(3.5 * 4.2, rel=1e-5)
    assert reloaded.rooms[0].ceiling_height.value == pytest.approx(2.7, rel=1e-5)
    assert len(reloaded.rooms[0].walls) == 4


def test_synthetic_point_cloud():
    """Verify synthetic room generates point clouds with correct bounding box and normals."""
    cfg = SyntheticRoomConfig(width=4.0, length=5.0, height=2.6, include_ceiling_sweep=True)
    synth = SyntheticRoom(cfg)
    pts, normals = synth.generate_point_cloud()
    
    assert pts.shape[0] > 5000
    assert normals.shape == pts.shape
    
    # Check bounds
    assert pts[:, 0].min() >= -0.1 and pts[:, 0].max() <= 4.1
    assert pts[:, 1].min() >= -0.1 and pts[:, 1].max() <= 5.1
    assert pts[:, 2].min() >= -0.1 and pts[:, 2].max() <= 2.7
