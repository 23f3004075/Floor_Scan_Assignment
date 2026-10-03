"""
CLI entry point for floorscan.

Usage:
    floorscan run <input> --out out/          # batch, auto-detects tier
    floorscan bench [--tier ...]              # run benchmark gates
    floorscan ablate-drift                    # drift correction ON vs OFF
    floorscan fixloop                         # regenerate before/after fix-loop
    floorscan repro                           # reproduce all reported numbers
    floorscan schema                          # export JSON schema
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from floorscan.schema import PropertyPlan, Tier, export_json_schema

app = typer.Typer(
    name="floorscan",
    help="Phone-captured whole-property floor plan pipeline.",
    no_args_is_help=True,
)
console = Console()


# ---------------------------------------------------------------------------
# Tier auto-detection
# ---------------------------------------------------------------------------

def detect_tier(input_path: Path) -> Tier:
    """
    Auto-detect the input tier from the directory/file structure.

    Rules:
    - If the path is a .mp4/.mov file -> VIDEO
    - If the path is a .zip file, check contents:
      - Contains depth/ folder + odometry.csv -> LIDAR
      - Contains .mp4/.mov -> VIDEO
    - If the path is a directory:
      - Contains depth/ + odometry.csv (or nested folder with them) -> LIDAR
      - Contains .mp4/.mov files -> VIDEO
      - Contains subdirectories with images (HEIC/JPG/PNG) -> PHOTO
      - Contains images directly -> PHOTO (single room)
    """
    if input_path.is_file():
        suffix = input_path.suffix.lower()
        if suffix == ".zip":
            return _detect_tier_from_zip(input_path)
        elif suffix in (".mp4", ".mov"):
            return Tier.VIDEO
        else:
            raise typer.BadParameter(f"Unsupported file type: {suffix}")

    if input_path.is_dir():
        return _detect_tier_from_dir(input_path)

    raise typer.BadParameter(f"Input path does not exist: {input_path}")


def _detect_tier_from_zip(zip_path: Path) -> Tier:
    """Detect tier from zip file contents."""
    import zipfile

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        has_depth = any("/depth/" in n or n.startswith("depth/") for n in names)
        has_odometry = any(n.endswith("odometry.csv") for n in names)
        has_video = any(n.endswith((".mp4", ".mov")) for n in names)

        if has_depth and has_odometry:
            return Tier.LIDAR
        elif has_video:
            return Tier.VIDEO
        else:
            return Tier.PHOTO


def _detect_tier_from_dir(dir_path: Path) -> Tier:
    """Detect tier from directory contents."""
    # Check for Stray Scanner layout (direct or one level nested)
    candidates = [dir_path] + [p for p in dir_path.iterdir() if p.is_dir()]
    for candidate in candidates:
        if (candidate / "depth").is_dir() and (candidate / "odometry.csv").is_file():
            return Tier.LIDAR

    # Check for video files
    video_exts = {".mp4", ".mov"}
    for f in dir_path.rglob("*"):
        if f.suffix.lower() in video_exts:
            return Tier.VIDEO

    # Check for image folders (photo tier)
    image_exts = {".heic", ".jpg", ".jpeg", ".png"}
    for f in dir_path.rglob("*"):
        if f.suffix.lower() in image_exts:
            return Tier.PHOTO

    raise typer.BadParameter(f"Cannot detect tier from: {dir_path}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command()
def run(
    input_path: Path = typer.Argument(..., help="Path to capture (folder, zip, or video file)"),
    out: Path = typer.Option(Path("out"), help="Output directory"),
    tier: Optional[str] = typer.Option(None, help="Force tier: lidar, video, photo, or auto"),
    seed: int = typer.Option(42, help="Random seed for determinism"),
) -> None:
    """Run the floor plan pipeline on a capture."""
    console.print(f"[bold blue]floorscan[/bold blue] v0.1.0")
    console.print(f"Input: {input_path}")

    # Resolve tier
    if tier and tier != "auto":
        resolved_tier = Tier(tier)
    else:
        resolved_tier = detect_tier(input_path)
    console.print(f"Tier: [bold green]{resolved_tier.value}[/bold green]")

    # Create output dir
    out.mkdir(parents=True, exist_ok=True)

    t0 = time.time()

    # Dispatch to tier pipeline
    if resolved_tier == Tier.LIDAR:
        plan = _run_lidar(input_path, out, seed)
    elif resolved_tier == Tier.VIDEO:
        plan = _run_video(input_path, out, seed)
    elif resolved_tier == Tier.PHOTO:
        plan = _run_photo(input_path, out, seed)
    else:
        raise typer.BadParameter(f"Unknown tier: {resolved_tier}")

    elapsed = time.time() - t0

    # Write outputs
    plan_json_path = out / "plan.json"
    plan.to_json(plan_json_path)
    console.print(f"[green][OK][/green] plan.json written to {plan_json_path}")

    # Write run manifest
    manifest = {
        "tier": resolved_tier.value,
        "input": str(input_path),
        "seed": seed,
        "elapsed_s": round(elapsed, 2),
        "version": "0.1.0",
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2))

    # Print summary
    _print_summary(plan, elapsed)


def _run_lidar(input_path: Path, out: Path, seed: int) -> PropertyPlan:
    """LiDAR tier pipeline."""
    from floorscan.io.stray_scanner import load_stray_capture
    from floorscan.geometry.gravity import estimate_gravity_and_convention
    from floorscan.geometry.planes import fit_floor_ceiling_planes, fit_wall_planes
    from floorscan.geometry.layout import extract_room_layout
    from floorscan.geometry.openings import detect_openings
    from floorscan.uncertainty.quality_gates import apply_quality_gates
    from floorscan.render.plan_svg import render_plan

    console.print("[cyan]Loading Stray Scanner capture...[/cyan]")
    capture = load_stray_capture(input_path)

    console.print("[cyan]Estimating gravity and axis convention...[/cyan]")
    scene = estimate_gravity_and_convention(capture, seed=seed)

    console.print("[cyan]Fitting floor/ceiling planes...[/cyan]")
    planes = fit_floor_ceiling_planes(scene)

    console.print("[cyan]Fitting wall planes...[/cyan]")
    walls = fit_wall_planes(scene, planes)

    console.print("[cyan]Extracting room layout...[/cyan]")
    layout = extract_room_layout(scene, planes, walls, seed=seed)

    console.print("[cyan]Detecting openings...[/cyan]")
    openings = detect_openings(scene, layout)

    console.print("[cyan]Applying quality gates...[/cyan]")
    plan = apply_quality_gates(layout, openings, planes, scene, tier=Tier.LIDAR)

    console.print("[cyan]Rendering plan...[/cyan]")
    render_plan(plan, out)

    return plan


def _run_video(input_path: Path, out: Path, seed: int) -> PropertyPlan:
    """Video tier pipeline (placeholder)."""
    console.print("[yellow]Video tier: not yet implemented, running skeleton...[/yellow]")
    from floorscan.schema import Measurement, NotObserved, RoomPlan, ConfidenceLevel
    plan = PropertyPlan(
        tier=Tier.VIDEO,
        rooms=[RoomPlan(
            room_id="room_1",
            room_name="Room 1",
            ceiling_height=NotObserved(
                reason="Video tier not yet implemented",
                tier=Tier.VIDEO,
            ),
        )],
    )
    return plan


def _run_photo(input_path: Path, out: Path, seed: int) -> PropertyPlan:
    """Photo tier pipeline (placeholder)."""
    console.print("[yellow]Photo tier: not yet implemented, running skeleton...[/yellow]")
    from floorscan.schema import NotObserved, RoomPlan
    plan = PropertyPlan(
        tier=Tier.PHOTO,
        rooms=[RoomPlan(
            room_id="room_1",
            room_name="Room 1",
            ceiling_height=NotObserved(
                reason="Photo tier not yet implemented",
                tier=Tier.PHOTO,
            ),
        )],
    )
    return plan


def _print_summary(plan: PropertyPlan, elapsed: float) -> None:
    """Print a summary table of the plan."""
    table = Table(title="Floor Plan Summary")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Tier", plan.tier.value)
    table.add_row("Rooms", str(len(plan.rooms)))
    for room in plan.rooms:
        n_walls = len(room.walls)
        n_openings = sum(len(w.openings) for w in room.walls)
        ch = room.ceiling_height
        if isinstance(ch, dict):
            ch_str = f"not_observed" if not ch.get("observed", True) else f"{ch.get('value', '?')}"
        elif hasattr(ch, "observed") and not ch.observed:
            ch_str = "not_observed"
        elif hasattr(ch, "value"):
            ch_str = f"{ch.value:.3f} m [{ch.ci_low:.3f}, {ch.ci_high:.3f}]"
        else:
            ch_str = str(ch)
        table.add_row(
            f"  {room.room_name or room.room_id}",
            f"{n_walls} walls, {n_openings} openings, ceiling: {ch_str}",
        )
    table.add_row("Runtime", f"{elapsed:.1f}s")

    console.print(table)


@app.command()
def schema(
    out: Path = typer.Option(Path("schema/floorscan_schema.json"), help="Output path"),
) -> None:
    """Export the JSON Schema for the output format."""
    export_json_schema(out)
    console.print(f"[green][OK][/green] Schema exported to {out}")


@app.command()
def bench(
    tier: Optional[str] = typer.Option(None, help="Tier to benchmark (or all)"),
    data_dir: Path = typer.Option(Path("data"), help="Data directory"),
    out: Path = typer.Option(Path("bench"), help="Benchmark output directory"),
) -> None:
    """Run benchmark gates on captured data with ground truth."""
    console.print("[yellow]Benchmark harness: not yet implemented[/yellow]")


@app.command(name="ablate-drift")
def ablate_drift(
    data_dir: Path = typer.Option(Path("data"), help="Data directory"),
    out: Path = typer.Option(Path("bench/drift_ablation"), help="Output directory"),
) -> None:
    """Run drift correction ablation: ON vs OFF, with overlay on ground truth."""
    console.print("[yellow]Drift ablation: not yet implemented[/yellow]")


@app.command()
def fixloop(
    out: Path = typer.Option(Path("bench"), help="Output directory"),
) -> None:
    """Regenerate fix-loop before/after results and diff table."""
    console.print("[yellow]Fix loop: not yet implemented[/yellow]")


@app.command()
def repro() -> None:
    """Reproduce all reported numbers from raw inputs."""
    console.print("[yellow]Reproduction bundle: not yet implemented[/yellow]")


if __name__ == "__main__":
    app()
