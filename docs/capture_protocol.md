# RoomScan Capture Protocol & Operator Guide

A rigorous, field-tested capture procedure designed for non-engineers to produce reliable, high-precision 3D scans across iPhone LiDAR, Video, and Photo tiers.

---

## 1. Golden Rules for All Tiers

1. **Continuous Smooth Motion:** Walk slowly (normal walking pace divided by two, ~0.3 m/s). Do not whip or jerk the phone.
2. **Loop Closure is Mandatory:** Always start at the primary room doorway and finish the capture facing the exact same doorway location. This enables loop-closure drift correction.
3. **The Ceiling Sweep (Crucial):**
   - The sample capture failed because the phone only pointed down (21°–42° pitch), missing 100% of the ceiling.
   - At the center of the room, perform a slow upward tilt sweep from eye level up to 75° towards the ceiling, hold for 2 seconds, and tilt smoothly back.
4. **Doorway Traversals for Multi-Room Captures:**
   - When passing between rooms, pause for 1 second in the doorway threshold.
   - Sweep both door jambs clearly so opening widths are unambiguously registered.
5. **Lighting & Reflection Hazards:**
   - Turn on all overhead room lights. Open blinds unless direct sunlight causes glare.
   - For full-length mirrors or large glass doors, cover with a small sticky note or tape an X if possible, or walk parallel rather than directly facing them.

---

## 2. Tier-Specific Capture Routes

### Tier 1: iPhone LiDAR Scan (Modes A & C - Stray Scanner / Live)
- **App:** Stray Scanner (free on App Store) or local web capture.
- **Settings:** 60 fps, 1920x1440 RGB, raw depth enabled.
- **Route:**
  1. Stand at the entrance door, phone held chest-high in landscape.
  2. Tap record. Walk the perimeter clockwise ~1.0 m from walls.
  3. Ensure baseboards and floor-wall joints are in frame.
  4. At the room center, execute the **Ceiling Sweep** (tilt up to ceiling, sweep 360°, tilt down).
  5. Scan across all door openings and window reveals at perpendicular angles.
  6. Return to entrance doorway, hold still for 1 second, and tap stop.

### Tier 2: Video Walkthrough (iPhone 15+ 4K/60fps)
- **Camera Settings:** Native iOS Camera app -> Video -> 4K at 60 fps or 1080p at 60 fps. Lock AE/AF (tap and hold center screen) to avoid auto-exposure jumps during SfM.
- **Scale Cue:** Place a standard A4 sheet of paper or credit card flat on the floor near the center of the room before starting.
- **Route:**
  1. Follow the exact same perimeter loop as LiDAR.
  2. Maintain continuous overlap between consecutive views (>= 70% visual overlap).
  3. Avoid standing in one spot and panning like a tripod; walk through the space to create baseline parallax.

### Tier 3: Photo Tier (Multi-Room Stills)
- **Folder Structure:** One folder per room, named sequentially in walking order:
  ```
  capture_photos/
    01_entrance_hall/
      IMG_0001.HEIC
      ...
    02_living_room/
      IMG_0010.HEIC
      ...
    03_kitchen/
      ...
  ```
- **Per-Room Protocol (4 to 8 photos per room):**
  1. **Corner 1:** Wide shot looking towards opposite corner.
  2. **Corner 2:** Wide shot towards opposite corner.
  3. **Corner 3:** Wide shot.
  4. **Corner 4:** Wide shot.
  5. **Doorway Connection Shot 1 (Looking Out):** Stand inside room, capture door frame showing the connected hallway.
  6. **Doorway Connection Shot 2 (Looking In):** Stand outside in hallway, capture through doorway into the room.
  *These doorway pairing shots provide the visual tie-points that enable multi-room topological stitching.*

---

## 3. Pre-Flight Checklist

- [ ] Battery >= 30% (prevents iOS thermal throttling of neural engine / LiDAR).
- [ ] Camera lens wiped clean of fingerprints.
- [ ] Room clutter picked up from baseboards if possible.
- [ ] All interior doors wedged fully open (do not move doors mid-scan).
- [ ] Scale cue card placed in center room for RGB video/photo tiers.
