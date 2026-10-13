#!/usr/bin/env python3
"""Create cached QGIS summary tables from a Firedrake ``results.h5`` file."""

from __future__ import annotations

import argparse
import csv
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import h5py
import numpy as np

COORDINATES_PATH = "/topologies/firedrake_default_topology/dms/firedrake_dm_1_0_0_False_2/vecs/firedrake_default_topology_coordinates/firedrake_default_topology_coordinates"
BATHYMETRY_PATH = "/topologies/firedrake_default_topology/dms/firedrake_dm_1_0_0_False_1/vecs/bathymetry/bathymetry"
VELOCITY_PATH = "/topologies/firedrake_default_topology/dms/firedrake_dm_1_0_0_False_2/vecs/uv_CG/uv_CG"
TOPOLOGY_ROOT = "/topologies/firedrake_default_topology"
COORDINATE_DM = f"{TOPOLOGY_ROOT}/dms/coordinateDM"
VELOCITY_DM = f"{TOPOLOGY_ROOT}/dms/firedrake_dm_1_0_0_False_2"
REFERENCE_XY = (492329.0, 6502216.0)
FLOOD_HEADING, EBB_HEADING = 110.0, 270.0
SEAWATER_DENSITY = 1025.0
CRS = "EPSG:32630"
CHUNK_SIZE = 64
VORTICITY_BATCH_SIZE = 8
DEFAULT_DURATION_DAYS = 0.5 * 29.53
TIDAL_DAY = timedelta(hours=24.84)


@dataclass(frozen=True)
class TidalWindow:
    name: str
    peak_index: int
    indices: np.ndarray


def parse_datetime(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid ISO 8601 datetime: {value}") from error
    return (result if result.tzinfo else result.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process hydrodynamic summary layers for QGIS.")
    parser.add_argument("results", nargs="?", type=Path, default=Path(__file__).resolve().parents[1] / "results.h5")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "layers")
    parser.add_argument("--start", type=parse_datetime, help="UTC start time (ISO 8601)")
    parser.add_argument("--days", type=float, help=f"duration in days; default: {DEFAULT_DURATION_DAYS}")
    parser.add_argument("--all-times", action="store_true", help="use the full source time range")
    parser.add_argument(
        "--neap-peaks-only",
        action="store_true",
        help="calculate only neap peak flood/ebb speeds without rebuilding other cached layers",
    )
    parser.add_argument("--flood-heading", type=float, default=FLOOD_HEADING)
    parser.add_argument("--ebb-heading", type=float, default=EBB_HEADING)
    parser.add_argument("--reference-x", type=float, default=REFERENCE_XY[0])
    parser.add_argument("--reference-y", type=float, default=REFERENCE_XY[1])
    return parser.parse_args()


def read_times(time_group: h5py.Group) -> list[datetime]:
    indexed_times = []
    for key, value in time_group.attrs.items():
        try:
            index = int(key)
        except ValueError as error:
            raise ValueError(f"Unexpected time attribute {key!r}") from error
        text = value.decode("utf-8") if isinstance(value, bytes) else str(value)
        timestamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
        indexed_times.append((index, (timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)))
    indexed_times.sort()
    if [index for index, _ in indexed_times] != list(range(len(indexed_times))):
        raise ValueError("Time attributes must be sequential indices starting at 0")
    return [timestamp for _, timestamp in indexed_times]


def select_time_indices(times: list[datetime], start: datetime | None, days: float | None) -> np.ndarray:
    if days is not None and days <= 0:
        raise ValueError("--days must be greater than zero")
    if start is None:
        start = times[0]
    end = start + timedelta(days=days) if days is not None else times[-1]
    if start < times[0] or end > times[-1]:
        raise ValueError(f"Requested period {start.isoformat()} to {end.isoformat()} is outside source coverage")
    result = np.asarray([index for index, value in enumerate(times) if start <= value <= end], dtype=np.int64)
    if not result.size:
        raise ValueError("The requested period contains no saved timesteps")
    return result


def nearest_node(x: np.ndarray, y: np.ndarray, point: tuple[float, float]) -> tuple[int, float]:
    distance_squared = (x - point[0]) ** 2 + (y - point[1]) ** 2
    index = int(np.argmin(distance_squared))
    return index, float(np.sqrt(distance_squared[index]))


def heading_degrees(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    return np.mod(np.degrees(np.arctan2(u, v)), 360.0)


def average_direction_degrees(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    direction = heading_degrees(u, v)
    direction[np.hypot(u, v) == 0] = np.nan
    return direction


def classify_flood_ebb(u: np.ndarray, v: np.ndarray, flood_heading: float, ebb_heading: float) -> tuple[np.ndarray, np.ndarray]:
    if not np.isfinite(flood_heading) or not np.isfinite(ebb_heading) or np.isclose((flood_heading - ebb_heading) % 360.0, 0.0):
        raise ValueError("Flood and ebb headings must be finite and different")
    heading = heading_degrees(u, v)
    flood_distance = np.abs((heading - flood_heading + 180.0) % 360.0 - 180.0)
    ebb_distance = np.abs((heading - ebb_heading + 180.0) % 360.0 - 180.0)
    valid = np.isfinite(u) & np.isfinite(v)
    return valid & (flood_distance < ebb_distance), valid & (flood_distance >= ebb_distance)


def make_accumulator(nodes: int) -> dict[str, np.ndarray]:
    return {name: np.zeros(nodes, dtype=np.float64) for name in ("count", "u", "v", "speed", "power")}


def accumulate(accumulator: dict[str, np.ndarray], u: np.ndarray, v: np.ndarray, mask: np.ndarray) -> None:
    if not np.any(mask):
        return
    selected_u, selected_v = u[mask], v[mask]
    valid = np.isfinite(selected_u) & np.isfinite(selected_v)
    speed = np.hypot(selected_u, selected_v)
    accumulator["count"] += valid.sum(axis=0)
    for name, values in (("u", selected_u), ("v", selected_v), ("speed", speed), ("power", 0.5 * SEAWATER_DENSITY * speed**3)):
        accumulator[name] += np.where(valid, values, 0.0).sum(axis=0)


def average(accumulator: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    result: dict[str, np.ndarray] = {}
    for name in ("u", "v", "speed", "power"):
        values = np.full(accumulator["count"].shape, np.nan)
        np.divide(accumulator[name], accumulator["count"], out=values, where=accumulator["count"] > 0)
        result[name] = values
    return result


def local_maximum_windows(times: list[datetime], selected: np.ndarray, reference_speed: np.ndarray) -> tuple[TidalWindow, TidalWindow]:
    half_window = TIDAL_DAY / 2
    candidates = [
        position for position in range(1, len(selected) - 1)
        if np.isfinite(reference_speed[position])
        and reference_speed[position] >= reference_speed[position - 1]
        and reference_speed[position] > reference_speed[position + 1]
        and times[selected[position]] - half_window >= times[selected[0]]
        and times[selected[position]] + half_window <= times[selected[-1]]
    ]
    if not candidates:
        raise ValueError("No local reference-speed maxima support a full 24.84-hour tidal-day window")
    def window(name: str, position: int) -> TidalWindow:
        centre = times[selected[position]]
        indices = selected[np.asarray([abs(times[index] - centre) <= half_window for index in selected])]
        return TidalWindow(name, int(selected[position]), indices)
    highest = max(candidates, key=lambda position: reference_speed[position])
    lowest = min(candidates, key=lambda position: reference_speed[position])
    return window("spring", highest), window("neap", lowest)


def topology_faces(h5_file: h5py.File, node_count: int, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    topology = h5_file[f"{TOPOLOGY_ROOT}/topology"]
    edge_vertices = topology["strata/1/cones"][...].ravel().reshape(-1, 2)
    face_edges = topology["strata/2/cones"][...].ravel().reshape(-1, 3)
    coordinate_order = h5_file[f"{COORDINATE_DM}/order"][...].ravel()
    velocity_order = h5_file[f"{VELOCITY_DM}/order"][...].ravel()
    offsets = h5_file[f"{VELOCITY_DM}/section/atlasOff"][...].ravel()
    dofs = h5_file[f"{VELOCITY_DM}/section/atlasDof"][...].ravel()
    if coordinate_order.size != node_count or np.unique(velocity_order).size != velocity_order.size:
        raise ValueError("Unexpected mesh ordering")
    global_to_chart = np.full(velocity_order.size, -1, dtype=np.int64)
    global_to_chart[velocity_order] = np.arange(velocity_order.size)
    chart = global_to_chart[coordinate_order]
    if np.any(chart < 0) or not np.all(dofs[chart] == 2):
        raise ValueError("Could not map vertices to velocity nodes")
    vertex_to_node = offsets[chart] // 2
    if np.any(offsets[chart] % 2) or np.unique(vertex_to_node).size != node_count:
        raise ValueError("Invalid velocity node mapping")
    faces = np.empty((face_edges.shape[0], 3), dtype=np.int64)
    xy = np.column_stack((x, y))
    for face_id, edges in enumerate(face_edges):
        vertices = np.unique(edge_vertices[edges])
        if vertices.size != 3:
            raise ValueError(f"Face {face_id} does not have three vertices")
        nodes = vertex_to_node[vertices]
        points = xy[nodes]
        centre = points.mean(axis=0)
        faces[face_id] = nodes[np.argsort(np.arctan2(points[:, 1] - centre[1], points[:, 0] - centre[0]))]
    return faces


def node_vorticity_batch(x: np.ndarray, y: np.ndarray, faces: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    x0, x1, x2 = (x[faces[:, column]] for column in range(3))
    y0, y1, y2 = (y[faces[:, column]] for column in range(3))
    determinant = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    valid_faces = np.isfinite(determinant) & ~np.isclose(determinant, 0.0)
    safe_determinant = np.where(valid_faces, determinant, 1.0)
    u_faces, v_faces = u[:, faces], v[:, faces]
    valid = valid_faces[None, :] & np.all(np.isfinite(u_faces) & np.isfinite(v_faces), axis=2)
    face_vorticity = (
        v_faces[:, :, 0] * (y1 - y2)
        + v_faces[:, :, 1] * (y2 - y0)
        + v_faces[:, :, 2] * (y0 - y1)
        + u_faces[:, :, 0] * (x1 - x2)
        + u_faces[:, :, 1] * (x2 - x0)
        + u_faces[:, :, 2] * (x0 - x1)
    ) / safe_determinant
    sums = np.zeros((u.shape[0], x.size))
    counts = np.zeros_like(sums)
    time_rows = np.arange(u.shape[0])[:, None]
    for corner in range(3):
        nodes = faces[None, :, corner]
        np.add.at(sums, (time_rows, nodes), np.where(valid, face_vorticity, 0.0))
        np.add.at(counts, (time_rows, nodes), valid)
    result = np.full_like(sums, np.nan)
    np.divide(sums, counts, out=result, where=counts > 0)
    return result


def save_layer(directory: Path, filename: str, x: np.ndarray, y: np.ndarray, fields: Iterable[tuple[str, np.ndarray]]) -> None:
    fields = list(fields)
    path, temporary = directory / filename, directory / f"{filename}.tmp"
    try:
        with temporary.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
            writer.writerow(("x", "y", *(name for name, _ in fields)))
            for row in np.column_stack((x, y, *(values for _, values in fields))):
                writer.writerow("" if not np.isfinite(value) else f"{value:.8f}" for value in row)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def read_velocity_rows(velocity: h5py.Dataset, indices: np.ndarray, node_count: int) -> np.ndarray:
    raw = np.asarray(velocity[indices[0]:indices[-1] + 1] if np.all(np.diff(indices) == 1) else velocity[indices])
    return raw.reshape(indices.size, node_count, 2)


def prepare_neap_peak_speeds(args: argparse.Namespace) -> None:
    if args.all_times and (args.start or args.days):
        raise ValueError("--all-times cannot be combined with --start or --days")
    selected_days = None if args.all_times else args.days if args.days is not None else DEFAULT_DURATION_DAYS
    metadata_path = args.output / "layer_metadata.txt"
    if not metadata_path.is_file():
        raise FileNotFoundError(
            f"Existing layer metadata is required for --neap-peaks-only: {metadata_path}"
        )
    metadata_lines = metadata_path.read_text(encoding="utf-8").splitlines()
    with h5py.File(args.results, "r") as source:
        times, velocity = read_times(source["time"]), source[VELOCITY_PATH]
        selected = select_time_indices(times, args.start, selected_days)
        expected_period = (
            f"Selected period: {times[selected[0]].isoformat()} to "
            f"{times[selected[-1]].isoformat()}"
        )
        if expected_period not in metadata_lines:
            raise ValueError(
                "The selected period does not match the existing cached layers"
            )
        coordinates = np.asarray(source[COORDINATES_PATH])
        if coordinates.ndim != 1 or coordinates.size % 2:
            raise ValueError("Unexpected coordinate dimensions")
        x, y = coordinates[0::2], coordinates[1::2]
        reference_index, _ = nearest_node(
            x, y, (args.reference_x, args.reference_y)
        )
        reference_speed = np.hypot(
            velocity[selected, 2 * reference_index],
            velocity[selected, 2 * reference_index + 1],
        )
        _, neap = local_maximum_windows(times, selected, reference_speed)
        if f"Neap tidal-day centre: {times[neap.peak_index].isoformat()}" not in metadata_lines:
            raise ValueError(
                "The neap tidal-day window does not match the existing cached layers"
            )
        reference_u = np.asarray(velocity[neap.indices, 2 * reference_index])
        reference_v = np.asarray(velocity[neap.indices, 2 * reference_index + 1])
        flood, ebb = classify_flood_ebb(
            reference_u,
            reference_v,
            args.flood_heading % 360.0,
            args.ebb_heading % 360.0,
        )
        snapshots = {}
        for kind, mask in (("flood", flood), ("ebb", ebb)):
            if not np.any(mask):
                raise ValueError(
                    f"Neap tidal-day window contains no {kind} timesteps"
                )
            local = np.flatnonzero(mask)[np.argmax(np.hypot(reference_u[mask], reference_v[mask]))]
            snapshot_index = int(neap.indices[local])
            snapshot = read_velocity_rows(
                velocity, np.asarray([snapshot_index]), x.size
            )[0]
            speed = np.hypot(snapshot[:, 0], snapshot[:, 1])
            save_layer(
                args.output,
                f"neap_peak_{kind}_speed.txt",
                x,
                y,
                [(f"neap_peak_{kind}_speed_m_s", speed)],
            )
            snapshots[kind] = times[snapshot_index]

    snapshot_prefixes = (
        "Neap peak flood snapshot: ",
        "Neap peak ebb snapshot: ",
    )
    metadata_lines = [
        line for line in metadata_lines
        if not line.startswith(snapshot_prefixes)
    ]
    metadata_lines.extend(
        f"Neap peak {kind} snapshot: {snapshot.isoformat()}"
        for kind, snapshot in snapshots.items()
    )
    temporary_path = metadata_path.with_suffix(".txt.tmp")
    temporary_path.write_text("\n".join(metadata_lines) + "\n", encoding="utf-8")
    temporary_path.replace(metadata_path)
    print(f"Wrote neap peak flood/ebb speed tables to {args.output}")


def process(args: argparse.Namespace) -> None:
    if not args.results.is_file():
        raise FileNotFoundError(f"Input HDF5 file not found: {args.results}")
    if args.all_times and (args.start or args.days):
        raise ValueError("--all-times cannot be combined with --start or --days")
    if args.neap_peaks_only:
        prepare_neap_peak_speeds(args)
        return
    selected_days = None if args.all_times else args.days if args.days is not None else DEFAULT_DURATION_DAYS
    args.output.mkdir(parents=True, exist_ok=True)
    with h5py.File(args.results, "r") as source:
        times, velocity = read_times(source["time"]), source[VELOCITY_PATH]
        selected = select_time_indices(times, args.start, selected_days)
        coordinates, bathymetry = np.asarray(source[COORDINATES_PATH]), np.asarray(source[BATHYMETRY_PATH])
        if coordinates.ndim != 1 or coordinates.size % 2 or velocity.shape != (len(times), coordinates.size):
            raise ValueError("Unexpected coordinate or interleaved velocity dimensions")
        x, y = coordinates[0::2], coordinates[1::2]
        if bathymetry.shape != x.shape:
            raise ValueError("Bathymetry does not match mesh node count")
        reference_index, reference_distance = nearest_node(x, y, (args.reference_x, args.reference_y))
        reference_speed = np.hypot(velocity[selected, 2 * reference_index], velocity[selected, 2 * reference_index + 1])
        spring, neap = local_maximum_windows(times, selected, reference_speed)
        windows = (spring, neap)
        window_indices = {window.name: window.indices for window in windows}
        accumulators = {name: make_accumulator(x.size) for name in ("all", "flood", "ebb", "spring", "spring_flood", "spring_ebb", "neap", "neap_flood", "neap_ebb")}
        spring_peak_reference_speed = {"flood": -np.inf, "ebb": -np.inf}
        spring_peak_node_speed: dict[str, np.ndarray] = {}
        spring_peak_times: dict[str, datetime] = {}
        vorticity_peaks = {
            kind: np.full(x.size, np.nan) for kind in ("flood", "ebb")
        }
        counts = {"flood": 0, "ebb": 0}
        faces = topology_faces(source, x.size, x, y)
        for offset in range(0, selected.size, CHUNK_SIZE):
            indices = selected[offset:offset + CHUNK_SIZE]
            uv = read_velocity_rows(velocity, indices, x.size)
            u, v = uv[:, :, 0], uv[:, :, 1]
            flood, ebb = classify_flood_ebb(u[:, reference_index], v[:, reference_index], args.flood_heading % 360.0, args.ebb_heading % 360.0)
            reference_speeds = np.hypot(u[:, reference_index], v[:, reference_index])
            for name, mask in (("all", np.ones(indices.size, dtype=bool)), ("flood", flood), ("ebb", ebb)):
                accumulate(accumulators[name], u, v, mask)
            counts["flood"] += int(flood.sum()); counts["ebb"] += int(ebb.sum())
            spring_window = np.isin(indices, window_indices["spring"])
            for kind, direction_mask in (("flood", flood), ("ebb", ebb)):
                mask = direction_mask & spring_window
                if np.any(mask):
                    local = np.flatnonzero(mask)[np.argmax(reference_speeds[mask])]
                    speed = float(reference_speeds[local])
                    if speed > spring_peak_reference_speed[kind]:
                        spring_peak_reference_speed[kind] = speed
                        spring_peak_node_speed[kind] = np.hypot(u[local], v[local])
                        spring_peak_times[kind] = times[indices[local]]
            for kind, direction_mask in (("flood", flood), ("ebb", ebb)):
                direction_rows = np.flatnonzero(direction_mask)
                for vorticity_offset in range(0, direction_rows.size, VORTICITY_BATCH_SIZE):
                    rows = direction_rows[vorticity_offset:vorticity_offset + VORTICITY_BATCH_SIZE]
                    vorticity = node_vorticity_batch(x, y, faces, u[rows], v[rows])
                    valid = np.isfinite(vorticity)
                    absolute = np.where(valid, np.abs(vorticity), -np.inf)
                    best_rows = np.argmax(absolute, axis=0)
                    columns = np.arange(x.size)
                    best_vorticity = vorticity[best_rows, columns]
                    has_values = np.any(valid, axis=0)
                    current_peak = vorticity_peaks[kind]
                    update = has_values & (
                        ~np.isfinite(current_peak)
                        | (np.abs(best_vorticity) > np.abs(current_peak))
                    )
                    current_peak[update] = best_vorticity[update]
            for window in windows:
                mask = np.isin(indices, window_indices[window.name])
                window_flood, window_ebb = flood & mask, ebb & mask
                accumulate(accumulators[window.name], u, v, mask)
                accumulate(accumulators[f"{window.name}_flood"], u, v, window_flood)
                accumulate(accumulators[f"{window.name}_ebb"], u, v, window_ebb)
        if not counts["flood"] or not counts["ebb"]:
            raise ValueError("Selected period must include flood and ebb timesteps")
        if set(spring_peak_node_speed) != {"flood", "ebb"}:
            raise ValueError("Spring tidal-day window must include flood and ebb timesteps")
    means = {name: average(value) for name, value in accumulators.items()}
    residual_speed = np.hypot(means["all"]["u"], means["all"]["v"])
    flood_speed, ebb_speed = means["flood"]["speed"], means["ebb"]["speed"]
    speed_sum = flood_speed + ebb_speed
    asymmetry = np.full(x.size, np.nan)
    np.divide(
        flood_speed - ebb_speed,
        speed_sum,
        out=asymmetry,
        where=np.isfinite(flood_speed) & np.isfinite(ebb_speed) & (speed_sum > 0),
    )
    save_layer(args.output, "bathymetry.txt", x, y, [("bathymetry_m", bathymetry)])
    save_layer(args.output, "mean_velocity.txt", x, y, [("mean_speed_m_s", means["all"]["speed"]), ("mean_direction_deg", average_direction_degrees(means["all"]["u"], means["all"]["v"]))])
    for kind in ("flood", "ebb"):
        values = means[kind]
        save_layer(args.output, f"mean_{kind}_velocity.txt", x, y, [("mean_speed_m_s", values["speed"]), ("mean_u_m_s", values["u"]), ("mean_v_m_s", values["v"]), ("mean_direction_deg", average_direction_degrees(values["u"], values["v"]))])
        save_layer(args.output, f"mean_{kind}_kinetic_power_density.txt", x, y, [("mean_power_density_W_m2", values["power"])])
    save_layer(args.output, "mean_kinetic_power_density.txt", x, y, [("mean_power_density_W_m2", means["all"]["power"])])
    save_layer(args.output, "residual_current.txt", x, y, [("residual_current_speed_m_s", residual_speed), ("residual_current_u_m_s", means["all"]["u"]), ("residual_current_v_m_s", means["all"]["v"])])
    save_layer(args.output, "flood_ebb_asymmetry.txt", x, y, [("flood_ebb_asymmetry", asymmetry)])
    for window in windows:
        for suffix, accumulator_name in (("mean_speed", window.name), ("mean_flood_speed", f"{window.name}_flood"), ("mean_ebb_speed", f"{window.name}_ebb")):
            save_layer(args.output, f"{window.name}_{suffix}.txt", x, y, [(f"{window.name}_{suffix}_m_s", means[accumulator_name]["speed"])])
    for kind, speed in spring_peak_node_speed.items():
        save_layer(args.output, f"spring_peak_{kind}_speed.txt", x, y, [(f"spring_peak_{kind}_speed_m_s", speed)])
    for kind in ("flood", "ebb"):
        vorticity = vorticity_peaks[kind]
        save_layer(args.output, f"peak_{kind}_vorticity.txt", x, y, [(f"peak_{kind}_vorticity_s_1", vorticity)])
    metadata = [f"Source: {args.results.resolve()}", f"Time coverage in source: {times[0].isoformat()} to {times[-1].isoformat()}", f"Selected period: {times[selected[0]].isoformat()} to {times[selected[-1]].isoformat()}", f"Selected timesteps: {selected.size}", f"Spring tidal-day centre: {times[spring.peak_index].isoformat()}", f"Spring peak flood snapshot: {spring_peak_times['flood'].isoformat()}", f"Spring peak ebb snapshot: {spring_peak_times['ebb'].isoformat()}", f"Neap tidal-day centre: {times[neap.peak_index].isoformat()}", f"Tidal-day window: {TIDAL_DAY.total_seconds() / 3600:.2f} hours", f"Classified as flood: {counts['flood']}", f"Classified as ebb: {counts['ebb']}", f"Reference point: ({args.reference_x:.2f}, {args.reference_y:.2f})", f"Nearest mesh node: ({x[reference_index]:.2f}, {y[reference_index]:.2f})", f"Distance to reference point: {reference_distance:.2f} m", f"CRS: {CRS}"]
    (args.output / "layer_metadata.txt").write_text("\n".join(metadata) + "\n", encoding="utf-8")
    print(f"Wrote cached QGIS layers for {selected.size} timesteps to {args.output}")


if __name__ == "__main__":
    process(parse_args())
