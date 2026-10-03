# Measurand Definitions

All pipeline measurements and ground-truth measurements use these definitions.

## Wall Length
**Definition:** Clear interior wall-to-wall distance measured at ~1.2 m height above the finished floor, clear of baseboards, trims, and any protrusions.
**Pipeline method:** Distance between intersection lines of adjacent wall planes.
**Ground truth method:** Laser distance meter, 3 repeats, at 1.2 m height, perpendicular to wall.
**Unit:** metres

## Ceiling Height
**Definition:** Vertical distance from the fitted floor plane to the fitted ceiling plane, measured as the difference in plane heights.
**Pipeline method:** |ceiling_plane.d - floor_plane.d| averaged over the overlap region. Both planes fitted within the same locally-anchored pose window when possible.
**Ground truth method:** Laser distance meter pointed vertically from floor, at ≥3 points per room (median).
**Unit:** metres
**Abstention:** If no ceiling plane is detected (insufficient points above 1.9m, or no horizontal plane in the ceiling height range), report `not_observed` with a prior range of [2.4, 3.6]m.

## Opening Width (Doors / Windows)
**Definition:** Clear opening width between jamb faces (the widest unobstructed passage).
**Pipeline method:** RGB edge detection → ray-plane intersection with the fitted wall plane → metric width. Multi-view fusion with consistency threshold.
**Ground truth method:** Tape measure between jambs, 3 repeats.
**Unit:** metres

## Opening Height
**Definition:** Clear opening height from sill (or floor for doors) to head of frame.
**Pipeline method:** Same ray-plane approach along the vertical axis.
**Ground truth method:** Tape measure from floor/sill to head, 3 repeats.
**Unit:** metres

## Floor Area
**Definition:** Area of the interior footprint polygon (wall-to-wall, not including wall thickness).
**Pipeline method:** Polygon area from Shapely, computed from the room polygon vertices.
**Ground truth method:** Computed from the measured polygon (wall lengths + diagonals checked).
**Unit:** m²

## Perimeter
**Definition:** Sum of wall lengths around the room.
**Pipeline method:** Sum of wall.length values.
**Ground truth method:** Sum of measured wall lengths.
**Unit:** metres

## Repeatability
**Definition:** For the same room captured twice at the same tier, the per-wall absolute difference in measured length.
**Gate:** ≤1 cm or 0.5% per wall (whichever is larger).

## Detection (Openings)
**Precision:** (correctly detected openings) / (total detections)
**Recall:** (correctly detected openings) / (total real openings)
**Matching rule:** An opening is "correctly detected" if its center position along the wall is within 30cm of a ground-truth opening center AND its type matches.
