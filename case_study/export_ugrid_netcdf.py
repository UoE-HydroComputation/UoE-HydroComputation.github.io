#!/usr/bin/env python3
"""Package cached mesh-node summaries as a QGIS-readable UGRID NetCDF."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import h5py
import netCDF4
import numpy as np
from pyproj import CRS


TOPOLOGY_ROOT = "/topologies/firedrake_default_topology"
COORDINATE_DM = f"{TOPOLOGY_ROOT}/dms/coordinateDM"
VELOCITY_DM = f"{TOPOLOGY_ROOT}/dms/firedrake_dm_1_0_0_False_2"
CRS_AUTHORITY = "EPSG:32630"

LAYERS = (
    ("bathymetry.txt", "bathymetry_m", "bathymetry", "Bathymetry", "m", "sea_floor_depth_below_geoid"),
    ("mean_velocity.txt", "mean_speed_m_s", "mean_speed", "Mean speed", "m s-1", "sea_water_speed"),
    ("mean_flood_velocity.txt", "mean_speed_m_s", "mean_flood_speed", "Mean flood speed", "m s-1", "sea_water_speed"),
    ("mean_flood_velocity.txt", "mean_u_m_s", "mean_flood_u", "u-component of Mean flood velocity", "m s-1", "eastward_sea_water_velocity"),
    ("mean_flood_velocity.txt", "mean_v_m_s", "mean_flood_v", "v-component of Mean flood velocity", "m s-1", "northward_sea_water_velocity"),
    ("mean_ebb_velocity.txt", "mean_speed_m_s", "mean_ebb_speed", "Mean ebb speed", "m s-1", "sea_water_speed"),
    ("mean_ebb_velocity.txt", "mean_u_m_s", "mean_ebb_u", "u-component of Mean ebb velocity", "m s-1", "eastward_sea_water_velocity"),
    ("mean_ebb_velocity.txt", "mean_v_m_s", "mean_ebb_v", "v-component of Mean ebb velocity", "m s-1", "northward_sea_water_velocity"),
    ("mean_kinetic_power_density.txt", "mean_power_density_W_m2", "mean_power_density", "Mean kinetic power density", "W m-2", ""),
    ("mean_flood_kinetic_power_density.txt", "mean_power_density_W_m2", "mean_flood_power_density", "Mean flood kinetic power density", "W m-2", ""),
    ("mean_ebb_kinetic_power_density.txt", "mean_power_density_W_m2", "mean_ebb_power_density", "Mean ebb kinetic power density", "W m-2", ""),
    ("residual_current.txt", "residual_current_speed_m_s", "residual_current_speed", "Residual current speed", "m s-1", "sea_water_speed"),
    ("residual_current.txt", "residual_current_u_m_s", "residual_current_u", "u-component of Residual current velocity", "m s-1", "eastward_sea_water_velocity"),
    ("residual_current.txt", "residual_current_v_m_s", "residual_current_v", "v-component of Residual current velocity", "m s-1", "northward_sea_water_velocity"),
    ("flood_ebb_asymmetry.txt", "flood_ebb_asymmetry", "flood_ebb_asymmetry", "Normalized flood-ebb speed asymmetry", "1", ""),
    ("spring_mean_speed.txt", "spring_mean_speed_m_s", "spring_mean_speed", "Daily spring tide mean speed", "m s-1", "sea_water_speed"),
    ("spring_mean_flood_speed.txt", "spring_mean_flood_speed_m_s", "spring_mean_flood_speed", "Daily spring tide mean flood speed", "m s-1", "sea_water_speed"),
    ("spring_mean_ebb_speed.txt", "spring_mean_ebb_speed_m_s", "spring_mean_ebb_speed", "Daily spring tide mean ebb speed", "m s-1", "sea_water_speed"),
    ("spring_peak_flood_speed.txt", "spring_peak_flood_speed_m_s", "spring_peak_flood_speed", "Peak spring flood speed", "m s-1", "sea_water_speed"),
    ("spring_peak_ebb_speed.txt", "spring_peak_ebb_speed_m_s", "spring_peak_ebb_speed", "Peak spring ebb speed", "m s-1", "sea_water_speed"),
    ("neap_mean_speed.txt", "neap_mean_speed_m_s", "neap_mean_speed", "Daily neap tide mean speed", "m s-1", "sea_water_speed"),
    ("neap_mean_flood_speed.txt", "neap_mean_flood_speed_m_s", "neap_mean_flood_speed", "Daily neap tide mean flood speed", "m s-1", "sea_water_speed"),
    ("neap_mean_ebb_speed.txt", "neap_mean_ebb_speed_m_s", "neap_mean_ebb_speed", "Daily neap tide mean ebb speed", "m s-1", "sea_water_speed"),
    ("neap_peak_flood_speed.txt", "neap_peak_flood_speed_m_s", "neap_peak_flood_speed", "Peak neap flood speed", "m s-1", "sea_water_speed"),
    ("neap_peak_ebb_speed.txt", "neap_peak_ebb_speed_m_s", "neap_peak_ebb_speed", "Peak neap ebb speed", "m s-1", "sea_water_speed"),
    ("peak_flood_vorticity.txt", "peak_flood_vorticity_s_1", "peak_flood_vorticity", "Peak flood vorticity", "s-1", ""),
    ("peak_ebb_vorticity.txt", "peak_ebb_vorticity_s_1", "peak_ebb_vorticity", "Peak ebb vorticity", "s-1", ""),
)

SUMMARY_GROUP_NAMES = frozenset((
    "Bathymetry", "Mean speed", "Mean flood speed",
    "Mean flood velocity", "Mean ebb speed",
    "Mean ebb velocity", "Mean kinetic power density",
    "Mean flood kinetic power density", "Mean ebb kinetic power density",
    "Residual current speed", "Residual current velocity",
    "Normalized flood-ebb speed asymmetry",
    "Daily spring tide mean speed", "Daily spring tide mean flood speed",
    "Daily spring tide mean ebb speed", "Daily neap tide mean speed",
    "Peak spring flood speed", "Peak spring ebb speed",
    "Daily neap tide mean flood speed", "Daily neap tide mean ebb speed",
    "Peak neap flood speed", "Peak neap ebb speed",
    "Peak flood vorticity", "Peak ebb vorticity",
))
VECTOR_GROUP_NAMES = frozenset((
    "Residual current velocity", "Mean flood velocity", "Mean ebb velocity",
))
VARIABLE_COMMENTS = {
    "peak_flood_vorticity": (
        "At each node, the signed flood-period vorticity with the largest "
        "absolute magnitude across all flood-classified timesteps in the "
        "selected period. Flood is classified from flow direction in the "
        "Inner Sound. Face-based derivatives are averaged at nodes, and "
        "different nodes may attain their extrema at different times."
    ),
    "peak_ebb_vorticity": (
        "At each node, the signed ebb-period vorticity with the largest "
        "absolute magnitude across all ebb-classified timesteps in the "
        "selected period. Ebb is classified from flow direction in the "
        "Inner Sound. Face-based derivatives are averaged at nodes, and "
        "different nodes may attain their extrema at different times."
    ),
    "spring_peak_flood_speed": (
        "Instantaneous speed at each node at the common timestamp within the "
        "24.84-hour spring tidal-day window when reference-node speed was "
        "highest among timesteps classified as flood from flow direction in "
        "the Inner Sound."
    ),
    "spring_peak_ebb_speed": (
        "Instantaneous speed at each node at the common timestamp within the "
        "24.84-hour spring tidal-day window when reference-node speed was "
        "highest among timesteps classified as ebb from flow direction in "
        "the Inner Sound."
    ),
    "neap_peak_flood_speed": (
        "Instantaneous speed at each node at the common timestamp within the "
        "24.84-hour neap tidal-day window when reference-node speed was "
        "highest among timesteps classified as flood from flow direction in "
        "the Inner Sound."
    ),
    "neap_peak_ebb_speed": (
        "Instantaneous speed at each node at the common timestamp within the "
        "24.84-hour neap tidal-day window when reference-node speed was "
        "highest among timesteps classified as ebb from flow direction in "
        "the Inner Sound."
    ),
}
SNAPSHOT_TIME_VARIABLES = frozenset((
    "spring_peak_flood_speed", "spring_peak_ebb_speed",
    "neap_peak_flood_speed", "neap_peak_ebb_speed",
))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package cached .txt summary layers into a UGRID NetCDF mesh."
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "results.h5",
        help="source HDF5 file used only to read mesh topology",
    )
    parser.add_argument(
        "--layers",
        type=Path,
        default=Path(__file__).resolve().parent / "layers",
        help="directory containing the processed .txt files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "layers" / "orkney_case_study.nc",
        help="output UGRID NetCDF file",
    )
    parser.add_argument(
        "--bathymetry-only",
        action="store_true",
        help="export only the bathymetry dataset",
    )
    parser.add_argument(
        "--decimal-places",
        type=int,
        default=4,
        help="decimal places retained in node data values (default: 4)",
    )
    return parser.parse_args()


def read_table(path: Path) -> np.ndarray:
    if not path.is_file():
        raise FileNotFoundError(f"Processed layer not found: {path}")
    table = np.genfromtxt(
        path,
        delimiter="\t",
        names=True,
        dtype=np.float64,
        encoding="utf-8",
        missing_values="",
        filling_values=np.nan,
    )
    if table.size == 0:
        raise ValueError(f"Processed layer is empty: {path}")
    return np.atleast_1d(table)


def read_processed_layers(layers_dir: Path, layers: tuple):
    tables = {}
    for filename, _, _, _, _, _ in layers:
        if filename not in tables:
            tables[filename] = read_table(layers_dir / filename)

    base = tables["bathymetry.txt"]
    if not {"x", "y"}.issubset(base.dtype.names or ()):
        raise ValueError("Layer tables must have x and y coordinate columns")
    x = base["x"]
    y = base["y"]
    for filename, table in tables.items():
        if table.size != base.size:
            raise ValueError(
                f"{filename} has {table.size} rows; expected {base.size}"
            )
        if not np.allclose(table["x"], x, rtol=0.0, atol=1e-7) or not np.allclose(
            table["y"], y, rtol=0.0, atol=1e-7
        ):
            raise ValueError(f"Coordinates in {filename} do not match bathymetry")
    return tables, x, y


def topology_connectivity(
    results_path: Path, node_count: int, x: np.ndarray, y: np.ndarray
) -> np.ndarray:
    with h5py.File(results_path, "r") as h5_file:
        topology = h5_file[f"{TOPOLOGY_ROOT}/topology"]
        vertex_count = h5_file[f"{TOPOLOGY_ROOT}/topology/strata/0/cone_sizes"].shape[0]
        edge_sizes = h5_file[f"{TOPOLOGY_ROOT}/topology/strata/1/cone_sizes"][...].ravel()
        face_sizes = h5_file[f"{TOPOLOGY_ROOT}/topology/strata/2/cone_sizes"][...].ravel()
        edge_vertices = topology["strata/1/cones"][...].ravel()
        face_edges = topology["strata/2/cones"][...].ravel()

        if vertex_count != node_count:
            raise ValueError(
                f"Mesh has {vertex_count} vertices but the text layers have "
                f"{node_count} nodes"
            )
        if not np.all(edge_sizes == 2) or not np.all(face_sizes == 3):
            raise ValueError("Expected a triangular mesh with two vertices per edge")
        edge_vertices = edge_vertices.reshape(-1, 2)
        face_edges = face_edges.reshape(-1, 3)
        if edge_vertices.min() < 0 or edge_vertices.max() >= vertex_count:
            raise ValueError("Mesh edge connectivity contains an invalid vertex")
        if face_edges.min() < 0 or face_edges.max() >= len(edge_vertices):
            raise ValueError("Mesh face connectivity contains an invalid edge")

        coordinate_order = h5_file[f"{COORDINATE_DM}/order"][...].ravel()
        velocity_order = h5_file[f"{VELOCITY_DM}/order"][...].ravel()
        velocity_offsets = h5_file[f"{VELOCITY_DM}/section/atlasOff"][...].ravel()
        velocity_dofs = h5_file[f"{VELOCITY_DM}/section/atlasDof"][...].ravel()

        if coordinate_order.size != vertex_count:
            raise ValueError("Unexpected coordinate-DM ordering size")
        global_point_to_chart = np.full(velocity_order.size, -1, dtype=np.int64)
        if (
            np.any(velocity_order < 0)
            or np.any(velocity_order >= velocity_order.size)
            or np.unique(velocity_order).size != velocity_order.size
        ):
            raise ValueError("Velocity-DM order is not a point-index permutation")
        global_point_to_chart[velocity_order] = np.arange(velocity_order.size)
        chart_points = global_point_to_chart[coordinate_order]
        if np.any(chart_points < 0) or not np.all(velocity_dofs[chart_points] == 2):
            raise ValueError("Could not map mesh vertices to velocity vector dofs")

        component_offsets = velocity_offsets[chart_points]
        if (
            np.any(component_offsets % 2)
            or np.any(component_offsets < 0)
            or np.any(component_offsets >= node_count * 2)
        ):
            raise ValueError("Invalid velocity-vector node offsets")
        vertex_to_node = component_offsets // 2
        if np.unique(vertex_to_node).size != node_count:
            raise ValueError("Velocity-vector offsets do not uniquely map all nodes")

    xy = np.column_stack((x, y))
    faces = np.empty((len(face_edges), 3), dtype=np.int32)
    for face_id, edge_ids in enumerate(face_edges):
        local_vertices = np.unique(edge_vertices[edge_ids])
        if local_vertices.size != 3:
            raise ValueError(f"Face {face_id} does not have exactly three vertices")
        node_ids = vertex_to_node[local_vertices]
        points = xy[node_ids]
        centre = points.mean(axis=0)
        angle = np.arctan2(points[:, 1] - centre[1], points[:, 0] - centre[0])
        faces[face_id] = node_ids[np.argsort(angle)]
    return faces


def read_period(metadata_path: Path) -> tuple[datetime, datetime]:
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Layer metadata not found: {metadata_path}")
    for line in metadata_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("Selected period: "):
            period = line.removeprefix("Selected period: ")
            start_text, separator, end_text = period.partition(" to ")
            if not separator:
                break
            start = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_text.replace("Z", "+00:00"))
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    raise ValueError(f"Selected period is missing from {metadata_path}")


def read_snapshot_times(metadata_path: Path) -> dict[str, datetime]:
    prefixes = {
        "spring_peak_flood_speed": "Spring peak flood snapshot: ",
        "spring_peak_ebb_speed": "Spring peak ebb snapshot: ",
        "neap_peak_flood_speed": "Neap peak flood snapshot: ",
        "neap_peak_ebb_speed": "Neap peak ebb snapshot: ",
    }
    snapshot_times = {}
    for line in metadata_path.read_text(encoding="utf-8").splitlines():
        for name, prefix in prefixes.items():
            if line.startswith(prefix):
                snapshot_times[name] = datetime.fromisoformat(line.removeprefix(prefix))
    return snapshot_times


def write_netcdf(
    output_path: Path,
    tables: dict[str, np.ndarray],
    x: np.ndarray,
    y: np.ndarray,
    faces: np.ndarray,
    period_start: datetime,
    period_end: datetime,
    layers: tuple,
    decimal_places: int,
    snapshot_times: dict[str, datetime],
) -> None:
    if decimal_places < 0:
        raise ValueError("--decimal-places must be zero or greater")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        with netCDF4.Dataset(temporary_path, "w", format="NETCDF4") as dataset:
            dataset.Conventions = "CF-1.8 UGRID-1.0"
            dataset.title = "Orkney tidal-flow case-study summary fields"
            dataset.source = "Processed Firedrake results.h5 summary layers"
            dataset.crs = CRS_AUTHORITY
            dataset.summary_period_start = period_start.isoformat()
            dataset.summary_period_end = period_end.isoformat()

            dataset.createDimension("node", x.size)
            dataset.createDimension("face", faces.shape[0])
            dataset.createDimension("max_face_nodes", 3)
            dataset.createDimension("time", 1)
            dataset.createDimension("bounds", 2)

            mesh = dataset.createVariable("mesh2d", "i4")
            mesh.cf_role = "mesh_topology"
            mesh.topology_dimension = 2
            mesh.node_coordinates = "mesh2d_node_x mesh2d_node_y"
            mesh.node_dimension = "node"
            mesh.face_node_connectivity = "mesh2d_face_nodes"
            mesh.face_dimension = "face"
            mesh.max_face_nodes_dimension = "max_face_nodes"

            x_var = dataset.createVariable("mesh2d_node_x", "f8", ("node",), zlib=True)
            y_var = dataset.createVariable("mesh2d_node_y", "f8", ("node",), zlib=True)
            for variable, standard_name, axis, values in (
                (x_var, "projection_x_coordinate", "X", x),
                (y_var, "projection_y_coordinate", "Y", y),
            ):
                variable[:] = values
                variable.standard_name = standard_name
                variable.axis = axis
                variable.units = "m"
                variable.mesh = "mesh2d"
                variable.location = "node"
                variable.grid_mapping = "crs"

            crs_var = dataset.createVariable("crs", "i4")
            crs_var.assignValue(0)
            crs = CRS.from_epsg(32630)
            crs_var.spatial_ref = crs.to_wkt()
            crs_var.crs_wkt = crs.to_wkt()
            crs_var.EPSG_code = CRS_AUTHORITY
            crs_var.epsg_code = CRS_AUTHORITY
            crs_var.epsg = 32630
            for name, value in crs.to_cf().items():
                if isinstance(value, (str, int, float, np.number)):
                    setattr(crs_var, name, value)

            connectivity = dataset.createVariable(
                "mesh2d_face_nodes",
                "i4",
                ("face", "max_face_nodes"),
                fill_value=-1,
                zlib=True,
                complevel=4,
            )
            connectivity.cf_role = "face_node_connectivity"
            connectivity.mesh = "mesh2d"
            connectivity.location = "face"
            connectivity.long_name = (
                "Mapping from every face to its corner nodes (counterclockwise)"
            )
            connectivity.start_index = 0
            connectivity[:] = faces

            time_var = dataset.createVariable("time", "f8", ("time",))
            time_var.standard_name = "time"
            time_var.units = "seconds since 1970-01-01 00:00:00 +00:00"
            time_var.calendar = "standard"
            time_var.bounds = "time_bounds"
            midpoint = period_start + (period_end - period_start) / 2
            time_var[0] = netCDF4.date2num(
                midpoint.replace(tzinfo=None), time_var.units, time_var.calendar
            )
            time_bounds = dataset.createVariable(
                "time_bounds", "f8", ("time", "bounds")
            )
            time_bounds[0, :] = netCDF4.date2num(
                [period_start.replace(tzinfo=None), period_end.replace(tzinfo=None)],
                time_var.units,
                time_var.calendar,
            )

            for filename, source_field, name, long_name, units, standard_name in layers:
                table = tables[filename]
                if source_field not in (table.dtype.names or ()):
                    raise ValueError(
                        f"Column {source_field!r} missing from {filename}"
                    )
                variable = dataset.createVariable(
                    name,
                    "f4",
                    ("time", "node"),
                    fill_value=np.float64(9.969209968386869e36),
                    zlib=True,
                    complevel=4,
                    shuffle=True,
                )
                variable.mesh = "mesh2d"
                variable.location = "node"
                variable.coordinates = "mesh2d_node_x mesh2d_node_y"
                variable.grid_mapping = "crs"
                variable.long_name = long_name
                variable.units = units
                if name in VARIABLE_COMMENTS:
                    variable.comment = VARIABLE_COMMENTS[name]
                if name in SNAPSHOT_TIME_VARIABLES:
                    if name not in snapshot_times:
                        raise ValueError(f"Snapshot time is missing for {name}")
                    variable.snapshot_time = snapshot_times[name].isoformat()
                if standard_name:
                    variable.standard_name = standard_name
                values = np.round(table[source_field], decimal_places)
                variable[0, :] = np.ma.masked_invalid(values)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    temporary_path.replace(output_path)


def main() -> None:
    args = parse_args()
    layers = LAYERS[:1] if args.bathymetry_only else LAYERS
    tables, x, y = read_processed_layers(args.layers, layers)
    faces = topology_connectivity(args.results, x.size, x, y)
    period_start, period_end = read_period(args.layers / "layer_metadata.txt")
    snapshot_times = read_snapshot_times(args.layers / "layer_metadata.txt")
    write_netcdf(
        args.output,
        tables,
        x,
        y,
        faces,
        period_start,
        period_end,
        layers,
        args.decimal_places,
        snapshot_times,
    )
    print(
        f"Wrote {args.output} with {x.size} nodes, {faces.shape[0]} triangular "
        f"faces, {len(layers)} node datasets rounded to {args.decimal_places} "
        f"decimal places."
    )


if __name__ == "__main__":
    main()
