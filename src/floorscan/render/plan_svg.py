"""
SVG/PNG floor plan renderer.

Produces a clean dimensioned floor plan showing:
- Room polygons with wall lengths and CI
- Openings (doors/windows)
- Ceiling height annotations
- Scale bar
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np

from floorscan.schema import PropertyPlan, RoomPlan, Wall, Measurement, NotObserved


# Colors
WALL_COLOR = "#2d3436"
FLOOR_COLOR = "#dfe6e9"
OPENING_COLOR = "#0984e3"
TEXT_COLOR = "#2d3436"
CI_COLOR = "#636e72"
BG_COLOR = "#ffffff"


def render_plan(plan: PropertyPlan, out_dir: Path) -> None:
    """
    Render the floor plan as SVG and PNG.

    Args:
        plan: PropertyPlan to render.
        out_dir: Output directory for plan.svg and plan.png.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(1, 1, figsize=(12, 10), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    all_x = []
    all_y = []

    for room in plan.rooms:
        _draw_room(ax, room, all_x, all_y)

    if all_x and all_y:
        margin = 0.5
        ax.set_xlim(min(all_x) - margin, max(all_x) + margin)
        ax.set_ylim(min(all_y) - margin, max(all_y) + margin)
    else:
        ax.set_xlim(-1, 5)
        ax.set_ylim(-1, 5)

    ax.set_aspect("equal")
    ax.set_xlabel("X (metres)", fontsize=10)
    ax.set_ylabel("Z (metres)", fontsize=10)

    # Title with tier info
    title = f"Floor Plan — {plan.tier.value.upper()} tier"
    if plan.rooms:
        room = plan.rooms[0]
        ch = room.ceiling_height
        if isinstance(ch, NotObserved) or (isinstance(ch, dict) and not ch.get("observed", True)):
            title += " | Ceiling: NOT OBSERVED"
        elif isinstance(ch, Measurement):
            title += f" | Ceiling: {ch.value:.2f}m [{ch.ci_low:.2f}, {ch.ci_high:.2f}]"
    ax.set_title(title, fontsize=14, fontweight="bold", pad=15)

    # Add floor area annotation
    if plan.total_floor_area and isinstance(plan.total_floor_area, Measurement):
        fa = plan.total_floor_area
        area_text = f"Floor Area: {fa.value:.2f} m² [{fa.ci_low:.2f}, {fa.ci_high:.2f}]"
        ax.annotate(
            area_text,
            xy=(0.02, 0.02), xycoords="axes fraction",
            fontsize=9, color=CI_COLOR,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#f5f6fa", edgecolor=CI_COLOR),
        )

    # Scale bar
    _add_scale_bar(ax, all_x, all_y)

    ax.grid(True, alpha=0.15, linestyle="--")
    plt.tight_layout()

    # Save
    svg_path = out_dir / "plan.svg"
    png_path = out_dir / "plan.png"
    fig.savefig(svg_path, format="svg", dpi=150, bbox_inches="tight")
    fig.savefig(png_path, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _draw_room(ax, room: RoomPlan, all_x: list, all_y: list) -> None:
    """Draw a single room on the axes."""
    if not room.floor_polygon:
        return

    # Draw filled polygon
    coords = [(p.x, p.y) for p in room.floor_polygon]
    if coords:
        polygon = plt.Polygon(coords, fill=True, facecolor=FLOOR_COLOR,
                              edgecolor=WALL_COLOR, linewidth=2.5, zorder=1)
        ax.add_patch(polygon)

        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        all_x.extend(xs)
        all_y.extend(ys)

    # Draw walls with dimension labels
    for wall in room.walls:
        x1, y1 = wall.start.x, wall.start.y
        x2, y2 = wall.end.x, wall.end.y

        # Wall line (already drawn by polygon, but we add dimension)
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2

        # Dimension label
        length = wall.length
        label = f"{length.value:.2f}m"
        ci_label = f"[{length.ci_low:.2f}, {length.ci_high:.2f}]"

        # Offset the label perpendicular to the wall
        dx = x2 - x1
        dy = y2 - y1
        wall_len = np.sqrt(dx**2 + dy**2)
        if wall_len > 0.01:
            nx = -dy / wall_len * 0.15
            ny = dx / wall_len * 0.15
        else:
            nx, ny = 0.1, 0.1

        ax.annotate(
            label,
            xy=(mid_x + nx, mid_y + ny),
            fontsize=8, fontweight="bold", color=TEXT_COLOR,
            ha="center", va="center",
        )
        ax.annotate(
            ci_label,
            xy=(mid_x + nx * 2, mid_y + ny * 2),
            fontsize=6, color=CI_COLOR,
            ha="center", va="center",
        )

    # Room name
    if room.floor_polygon:
        cx = np.mean([p.x for p in room.floor_polygon])
        cy = np.mean([p.y for p in room.floor_polygon])
        ax.text(
            cx, cy, room.room_name or room.room_id,
            fontsize=11, fontweight="bold", color=TEXT_COLOR,
            ha="center", va="center", alpha=0.6,
        )


def _add_scale_bar(ax, all_x: list, all_y: list) -> None:
    """Add a 1-metre scale bar."""
    if not all_x or not all_y:
        return

    x_range = max(all_x) - min(all_x)
    bar_x = min(all_x) - 0.3
    bar_y = min(all_y) - 0.4

    ax.plot([bar_x, bar_x + 1.0], [bar_y, bar_y],
            color=WALL_COLOR, linewidth=3, solid_capstyle="butt")
    ax.text(bar_x + 0.5, bar_y - 0.1, "1 m",
            fontsize=9, ha="center", color=TEXT_COLOR)
