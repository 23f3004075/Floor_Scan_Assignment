"""
Pydantic v2 schema for floorscan output.

Every measurement carries a calibrated confidence interval.
JSON Schema is exported for validation.
All fields marked [provisional] until the published Round-1 schema is received.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Tier(str, Enum):
    LIDAR = "lidar"
    VIDEO = "video"
    PHOTO = "photo"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NOT_OBSERVED = "not_observed"


class DamageClass(str, Enum):
    WATER_STAIN = "water_stain"
    MOULD = "mould"
    CRACK = "crack"
    PEELING_PAINT = "peeling_paint"
    EFFLORESCENCE = "efflorescence"
    DISCOLOURATION = "discolouration"
    OTHER = "other"


class OpeningType(str, Enum):
    DOOR = "door"
    WINDOW = "window"
    ARCHWAY = "archway"
    PASS_THROUGH = "pass_through"


class SurfaceType(str, Enum):
    WALL = "wall"
    FLOOR = "floor"
    CEILING = "ceiling"


# ---------------------------------------------------------------------------
# Measurement with CI
# ---------------------------------------------------------------------------

class Measurement(BaseModel):
    """A single metric measurement with a calibrated confidence interval."""
    value: float = Field(..., description="Best-estimate value in metres (or m² for area)")
    ci_low: float = Field(..., description="Lower bound of confidence interval")
    ci_high: float = Field(..., description="Upper bound of confidence interval")
    confidence_level: ConfidenceLevel = Field(
        default=ConfidenceLevel.HIGH,
        description="Qualitative confidence flag"
    )
    ci_level: float = Field(default=0.90, description="Nominal coverage probability")
    method: str = Field(default="", description="How this measurement was derived")
    tier: Tier = Field(..., description="Input tier that produced this measurement")
    flags: list[str] = Field(default_factory=list, description="Quality/warning flags")


class NotObserved(BaseModel):
    """Sentinel for a measurement that could not be made (e.g., ceiling never seen)."""
    observed: bool = Field(default=False)
    reason: str = Field(default="")
    prior_low: Optional[float] = Field(default=None, description="Prior lower bound (m)")
    prior_high: Optional[float] = Field(default=None, description="Prior upper bound (m)")
    confidence_level: ConfidenceLevel = Field(default=ConfidenceLevel.NOT_OBSERVED)
    tier: Tier = Field(..., description="Input tier")


# ---------------------------------------------------------------------------
# Geometry primitives
# ---------------------------------------------------------------------------

class Point2D(BaseModel):
    x: float
    y: float


class Point3D(BaseModel):
    x: float
    y: float
    z: float


# ---------------------------------------------------------------------------
# Opening (door / window)
# ---------------------------------------------------------------------------

class Opening(BaseModel):
    """A detected opening (door, window, etc.) on a wall surface."""
    opening_id: str = Field(..., description="Unique opening identifier")
    opening_type: OpeningType
    wall_id: str = Field(..., description="ID of the wall this opening belongs to")
    width: Measurement = Field(..., description="Clear opening width (m)")
    height: Optional[Measurement] = Field(default=None, description="Opening height (m)")
    position_along_wall: Optional[float] = Field(
        default=None, description="Distance from wall start to opening center (m)"
    )
    connects_to_room: Optional[str] = Field(
        default=None, description="Room ID on the other side (if door/pass-through)"
    )
    detection_confidence: float = Field(
        default=1.0, description="Detection confidence [0,1]"
    )
    num_views: int = Field(default=0, description="Number of views where this opening was seen")


# ---------------------------------------------------------------------------
# Wall
# ---------------------------------------------------------------------------

class Wall(BaseModel):
    """A single wall segment in a room."""
    wall_id: str
    start: Point2D = Field(..., description="Start point of wall in floor plan (m)")
    end: Point2D = Field(..., description="End point of wall in floor plan (m)")
    length: Measurement = Field(..., description="Wall length (m)")
    normal: Optional[Point2D] = Field(default=None, description="Inward-facing normal (unit)")
    surface_id: str = Field(default="", description="Surface ID for scope/damage keying")
    openings: list[Opening] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Damage region
# ---------------------------------------------------------------------------

class DamageRegion(BaseModel):
    """A detected damage region on a surface."""
    damage_id: str
    damage_class: DamageClass
    surface_id: str = Field(..., description="Surface this damage is on")
    surface_type: SurfaceType
    area: Optional[Measurement] = Field(default=None, description="Damaged area (m²)")
    length: Optional[Measurement] = Field(default=None, description="Damage extent length (m)")
    bounding_box_2d: Optional[list[Point2D]] = Field(
        default=None, description="Bounding polygon on the floor plan"
    )
    detection_confidence: float = Field(default=1.0)


# ---------------------------------------------------------------------------
# Concealed-damage flag
# ---------------------------------------------------------------------------

class ConcealedDamageFlag(BaseModel):
    """A rule-based flag for possible concealed damage."""
    flag_id: str
    rule_id: str = Field(..., description="ID from the rules YAML")
    rule_description: str = Field(default="")
    surface_id: str
    inputs: dict = Field(
        default_factory=dict,
        description="Evidence that triggered the rule (e.g., stain location, proximity)"
    )
    fired_condition: str = Field(default="", description="Human-readable condition that fired")
    confidence: float = Field(default=0.5, description="Rule confidence [0,1]")


# ---------------------------------------------------------------------------
# Scope line item
# ---------------------------------------------------------------------------

class ScopeLineItem(BaseModel):
    """A remediation scope line item keyed to a surface."""
    item_id: str
    surface_id: str
    description: str = Field(..., description="e.g., 'Drywall repair', 'Repaint ceiling'")
    damage_id: Optional[str] = Field(default=None)
    quantity: Optional[Measurement] = Field(default=None, description="Quantity (m² or m)")
    unit: str = Field(default="m²")


# ---------------------------------------------------------------------------
# Room plan
# ---------------------------------------------------------------------------

class RoomPlan(BaseModel):
    """Per-room plan with walls, ceiling height, floor area, openings, damage."""
    room_id: str
    room_name: str = Field(default="")
    walls: list[Wall] = Field(default_factory=list)
    floor_polygon: list[Point2D] = Field(
        default_factory=list, description="Ordered vertices of room footprint (m)"
    )
    floor_area: Optional[Measurement] = Field(default=None, description="Floor area (m²)")
    ceiling_height: Measurement | NotObserved = Field(
        ..., description="Ceiling height or not_observed sentinel"
    )
    perimeter: Optional[Measurement] = Field(default=None, description="Room perimeter (m)")
    damage_regions: list[DamageRegion] = Field(default_factory=list)
    concealed_damage_flags: list[ConcealedDamageFlag] = Field(default_factory=list)
    scope_items: list[ScopeLineItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Adjacency edge
# ---------------------------------------------------------------------------

class AdjacencyEdge(BaseModel):
    """An adjacency relationship between two rooms."""
    room_a: str
    room_b: str
    shared_opening_id: Optional[str] = Field(default=None)
    confidence: float = Field(default=1.0, description="Adjacency confidence [0,1]")
    evidence: list[str] = Field(
        default_factory=list,
        description="Evidence sources: 'shared_wall', 'doorway_match', 'folder_order', etc."
    )


# ---------------------------------------------------------------------------
# Property plan (top-level output)
# ---------------------------------------------------------------------------

class PropertyPlan(BaseModel):
    """The top-level output: a stitched whole-property floor plan."""
    property_id: str = Field(default="scan_001")
    tier: Tier
    rooms: list[RoomPlan] = Field(default_factory=list)
    adjacency: list[AdjacencyEdge] = Field(default_factory=list)
    total_floor_area: Optional[Measurement] = Field(default=None, description="Total area (m²)")
    total_perimeter: Optional[Measurement] = Field(default=None, description="Total perimeter (m)")
    metadata: dict = Field(default_factory=dict, description="Provenance, timing, versions")

    def to_json(self, path: str | Path) -> None:
        """Write the plan as validated JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def from_json(cls, path: str | Path) -> "PropertyPlan":
        """Load and validate a plan from JSON."""
        path = Path(path)
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# JSON Schema export
# ---------------------------------------------------------------------------

def export_json_schema(path: str | Path = "schema/floorscan_schema.json") -> None:
    """Export the JSON Schema for PropertyPlan."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = PropertyPlan.model_json_schema()
    path.write_text(json.dumps(schema, indent=2), encoding="utf-8")


if __name__ == "__main__":
    export_json_schema()
    print("Schema exported to schema/floorscan_schema.json")
