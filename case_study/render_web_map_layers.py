#!/usr/bin/env python3
"""Render compact Web Mercator overlays for the Orkney case-study web map."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from pyproj import Transformer
from export_ugrid_netcdf import topology_connectivity


ROOT = Path(__file__).resolve().parents[1]
LAYERS_DIR = Path(__file__).resolve().parent / "layers"
OUTPUT_DIR = ROOT / "_static" / "case-study"
RESULTS_PATH = ROOT / "results.h5"
SITES_PATH = LAYERS_DIR / "lease-sites" / "tidal_lease_sites_all.shp"
DOMAIN_PATH = ROOT / "OrkneysAdjoint-v0.shp"
SITE_DISPLAY_OVERRIDES = {
    "Brims Tidal Array": {
        "Name_Ten": "None",
        "Lease_Stat": "None",
        "Inf_Status": "Historic feasibility study",
    },
    "Brough Ness": {
        "Name_Ten": "None",
        "Lease_Stat": "None",
        "Inf_Status": "Historic feasibility study",
    },
    "Ness of Duncansby": {
        "Name_Ten": "None",
        "Lease_Stat": "None",
        "Inf_Status": "Historic feasibility study",
    },
    "Lashy Sound": {
        "Name_Ten": "None",
        "Lease_Stat": "None",
        "Inf_Status": "Historic feasibility study",
    },
    "EMEC Stronsay Firth": {
        "Name_Ten": "None",
        "Lease_Stat": "None",
        "Inf_Status": "Historic feasibility study",
    },
    "Westray South": {
        "Name_Ten": "Orbital Marine Power",
        "Inf_Status": "Consenting",
    },
    "Fall of Warness": {
        "Inf_Status": "Active/In Operation",
    },
    "EMEC Shapinsay Sound": {
        "Inf_Status": "Pre-planning Application",
    },
}
RASTER_WIDTH = 3000
MIN_ZOOM = 7
MAX_ZOOM = 11
WEB_MERCATOR_LIMIT = 20037508.342789244
DETAIL_RASTER_WIDTH = 2048
DETAIL_MIN_ZOOM = 12
DETAIL_MAX_ZOOM = 13
DETAIL_REGIONS = {
    "pentland-firth": (480000, 6495000, 510000, 6518000),
    "westray-stronsay": (500000, 6535000, 525000, 6570000),
}
DETAIL_LAYER_SLUGS = frozenset((
    "bathymetry",
    "mean-speed",
    "mean-flood-speed",
    "mean-ebb-speed",
    "mean-power-density",
    "mean-flood-power-density",
    "mean-ebb-power-density",
    "residual-current-speed",
    "flood-ebb-asymmetry",
    "spring-mean-speed",
    "spring-mean-flood-speed",
    "spring-mean-ebb-speed",
    "spring-peak-flood-speed",
    "spring-peak-ebb-speed",
    "neap-mean-speed",
    "neap-mean-flood-speed",
    "neap-mean-ebb-speed",
    "neap-peak-flood-speed",
    "neap-peak-ebb-speed",
    "peak-flood-vorticity",
    "peak-ebb-vorticity",
))
NODATA_VALUE = -9999

LAYER_SPECS = (
    ("bathymetry", "bathymetry.txt", "bathymetry_m", "Bathymetry", "m", 0, 200, "bathymetry"),
    ("mean-speed", "mean_velocity.txt", "mean_speed_m_s", "Mean speed", "m/s", 0, 2.5, "linear"),
    ("mean-flood-speed", "mean_flood_velocity.txt", "mean_speed_m_s", "Mean flood speed", "m/s", 0, 3, "linear"),
    ("mean-ebb-speed", "mean_ebb_velocity.txt", "mean_speed_m_s", "Mean ebb speed", "m/s", 0, 2.5, "linear"),
    ("mean-power-density", "mean_kinetic_power_density.txt", "mean_power_density_W_m2", "Mean kinetic power density", "W/m²", 0, 15000, "power-density"),
    ("mean-flood-power-density", "mean_flood_kinetic_power_density.txt", "mean_power_density_W_m2", "Mean flood kinetic power density", "W/m²", 0, 15000, "power-density"),
    ("mean-ebb-power-density", "mean_ebb_kinetic_power_density.txt", "mean_power_density_W_m2", "Mean ebb kinetic power density", "W/m²", 0, 15000, "power-density"),
    ("residual-current-speed", "residual_current.txt", "residual_current_speed_m_s", "Residual current speed", "m/s", 0, 1.25, "linear"),
    ("flood-ebb-asymmetry", "flood_ebb_asymmetry.txt", "flood_ebb_asymmetry", "Normalized flood–ebb asymmetry", "", -1, 1, "diverging"),
    ("spring-mean-speed", "spring_mean_speed.txt", "spring_mean_speed_m_s", "Daily spring tide mean speed", "m/s", 0, 4, "linear"),
    ("spring-mean-flood-speed", "spring_mean_flood_speed.txt", "spring_mean_flood_speed_m_s", "Daily spring tide mean flood speed", "m/s", 0, 4, "linear"),
    ("spring-mean-ebb-speed", "spring_mean_ebb_speed.txt", "spring_mean_ebb_speed_m_s", "Daily spring tide mean ebb speed", "m/s", 0, 4, "linear"),
    ("spring-peak-flood-speed", "spring_peak_flood_speed.txt", "spring_peak_flood_speed_m_s", "Peak spring flood speed", "m/s", 0, 6, "linear"),
    ("spring-peak-ebb-speed", "spring_peak_ebb_speed.txt", "spring_peak_ebb_speed_m_s", "Peak spring ebb speed", "m/s", 0, 6, "linear"),
    ("neap-mean-speed", "neap_mean_speed.txt", "neap_mean_speed_m_s", "Daily neap tide mean speed", "m/s", 0, 3, "linear"),
    ("neap-mean-flood-speed", "neap_mean_flood_speed.txt", "neap_mean_flood_speed_m_s", "Daily neap tide mean flood speed", "m/s", 0, 3, "linear"),
    ("neap-mean-ebb-speed", "neap_mean_ebb_speed.txt", "neap_mean_ebb_speed_m_s", "Daily neap tide mean ebb speed", "m/s", 0, 3, "linear"),
    ("neap-peak-flood-speed", "neap_peak_flood_speed.txt", "neap_peak_flood_speed_m_s", "Peak neap flood speed", "m/s", 0, 5, "linear"),
    ("neap-peak-ebb-speed", "neap_peak_ebb_speed.txt", "neap_peak_ebb_speed_m_s", "Peak neap ebb speed", "m/s", 0, 5, "linear"),
    ("peak-flood-vorticity", "peak_flood_vorticity.txt", "peak_flood_vorticity_s_1", "Peak flood vorticity", "s⁻¹", -0.05, 0.05, "diverging"),
    ("peak-ebb-vorticity", "peak_ebb_vorticity.txt", "peak_ebb_vorticity_s_1", "Peak ebb vorticity", "s⁻¹", -0.05, 0.05, "diverging"),
)

SEQUENTIAL_COLOURS = ("#ffffff", "#c7e9f1", "#78c6d0", "#3196b2", "#176493", "#08306b")
DIVERGING_COLOURS = ("#762a83", "#c2a5cf", "#f7f7f7", "#a6dba0", "#1b7837")
POWER_DENSITY_COLOURS = ("#fff7bc", "#fdae61", "#a50026")
BATHYMETRY_COLOURS = ("#d9f0f0", "#91c9d0", "#4a9fb8", "#276a9f", "#174375", "#081d58")
FLOW_ARROW_SPECS = {
    "mean-flood-speed": ("mean_flood_velocity.txt", "mean_u_m_s", "mean_v_m_s", 7000, 0.1),
    "mean-ebb-speed": ("mean_ebb_velocity.txt", "mean_u_m_s", "mean_v_m_s", 7000, 0.1),
    "residual-current-speed": ("residual_current.txt", "residual_current_u_m_s", "residual_current_v_m_s", 5000, 0.1),
}


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def read_layers() -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray]:
    tables: dict[str, np.ndarray] = {}
    x = y = None
    for _, filename, field, *_ in LAYER_SPECS:
        if filename not in tables:
            table = np.genfromtxt(
                LAYERS_DIR / filename,
                delimiter="\t",
                names=True,
                dtype=np.float64,
                encoding="utf-8",
            )
            tables[filename] = np.atleast_1d(table)
        table = tables[filename]
        if field not in table.dtype.names:
            raise ValueError(f"{filename} does not contain {field}")
        if x is None:
            x, y = table["x"], table["y"]
        elif not np.array_equal(x, table["x"]) or not np.array_equal(y, table["y"]):
            raise ValueError(f"Coordinates in {filename} do not match the base layer")
    return tables, x, y


def write_faces_csv(path: Path, tables: dict[str, np.ndarray], x: np.ndarray, y: np.ndarray) -> None:
    faces = topology_connectivity(RESULTS_PATH, len(x), x, y)
    fields = [spec[0] for spec in LAYER_SPECS]
    values = {
        slug: tables[filename][column]
        for slug, filename, column, *_ in LAYER_SPECS
    }
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(("WKT", *fields, "wet"))
        for face in faces:
            points = ", ".join(f"{x[node]:.8f} {y[node]:.8f}" for node in (*face, face[0]))
            writer.writerow((
                f"POLYGON (({points}))",
                *(float(values[field][face].mean()) for field in fields),
                1,
            ))


def sample_flow_arrows(
    tables: dict[str, np.ndarray], x: np.ndarray, y: np.ndarray,
) -> dict[str, list[tuple[float, float, float, float]]]:
    output = {}
    for layer, (filename, u_field, v_field, spacing, minimum_speed) in FLOW_ARROW_SPECS.items():
        table = tables[filename]
        u, v = table[u_field], table[v_field]
        speed = np.hypot(u, v)
        valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(speed) & (speed >= minimum_speed)
        candidates = np.flatnonzero(valid)
        cell_x = np.floor(x / spacing).astype(np.int64)
        cell_y = np.floor(y / spacing).astype(np.int64)
        centre_x = (cell_x[candidates] + 0.5) * spacing
        centre_y = (cell_y[candidates] + 0.5) * spacing
        distance = (x[candidates] - centre_x) ** 2 + (y[candidates] - centre_y) ** 2
        order = np.lexsort((distance, cell_y[candidates], cell_x[candidates]))
        ordered = candidates[order]
        ordered_x, ordered_y = cell_x[ordered], cell_y[ordered]
        first_in_cell = np.ones(ordered.size, dtype=bool)
        first_in_cell[1:] = (
            (ordered_x[1:] != ordered_x[:-1])
            | (ordered_y[1:] != ordered_y[:-1])
        )
        selected = ordered[first_in_cell]
        output[layer] = [
            (float(x[index]), float(y[index]), float(u[index]), float(v[index]))
            for index in selected
        ]
    return output


def arrow_polygon(
    x: float, y: float, direction_x: float, direction_y: float, scale: float,
) -> str:
    perpendicular_x, perpendicular_y = -direction_y, direction_x
    shape = (
        (7, 0), (1.5, -2.5), (1.5, -0.7), (-6, -0.7),
        (-6, 0.7), (1.5, 0.7), (1.5, 2.5),
    )
    points = [
        f"{x + scale * (along * direction_x + across * perpendicular_x):.2f},"
        f"{y + scale * (along * direction_y + across * perpendicular_y):.2f}"
        for along, across in shape
    ]
    return "polygon " + " ".join(points)


def bake_flow_arrows(
    tile_directory: Path,
    arrows: list[tuple[float, float, float, float]],
    minimum_zoom: int,
    maximum_zoom: int,
) -> int:
    if not arrows:
        return 0
    transformer = Transformer.from_crs("EPSG:32630", "EPSG:3857", always_xy=True)
    coordinates = np.asarray(arrows, dtype=np.float64)
    x, y, u, v = coordinates.T
    speed = np.hypot(u, v)
    end_x, end_y = transformer.transform(x + 1000 * u / speed, y + 1000 * v / speed)
    map_x, map_y = transformer.transform(x, y)
    directions_x = end_x - map_x
    directions_y = map_y - end_y
    direction_lengths = np.hypot(directions_x, directions_y)
    directions_x /= direction_lengths
    directions_y /= direction_lengths
    tiles_updated = 0
    for zoom in range(minimum_zoom, maximum_zoom + 1):
        pixel_size = 2 * WEB_MERCATOR_LIMIT / (256 * (2 ** zoom))
        pixel_x = (map_x + WEB_MERCATOR_LIMIT) / pixel_size
        pixel_y = (WEB_MERCATOR_LIMIT - map_y) / pixel_size
        tile_x = np.floor(pixel_x / 256).astype(np.int64)
        tile_y = np.floor(pixel_y / 256).astype(np.int64)
        arrows_by_tile: dict[tuple[int, int], list[str]] = {}
        for index in range(len(arrows)):
            local_x = pixel_x[index] - tile_x[index] * 256
            local_y = pixel_y[index] - tile_y[index] * 256
            outer = arrow_polygon(local_x, local_y, directions_x[index], directions_y[index], 1.35)
            inner = arrow_polygon(local_x, local_y, directions_x[index], directions_y[index], 1)
            arrows_by_tile.setdefault((int(tile_x[index]), int(tile_y[index])), []).extend(
                (outer, inner)
            )

        for (x_index, y_index), polygons in arrows_by_tile.items():
            tile = tile_directory / str(zoom) / str(x_index) / f"{y_index}.webp"
            if not tile.is_file():
                continue
            outer_polygons = " ".join(polygons[::2])
            inner_polygons = " ".join(polygons[1::2])
            temporary = tile.with_name(f".{tile.stem}.arrows.webp")
            run(
                "convert", str(tile),
                "-fill", "#ffffff", "-stroke", "none", "-draw", outer_polygons,
                "-fill", "#102f45", "-draw", inner_polygons,
                "-quality", "90", str(temporary),
            )
            temporary.replace(tile)
            tiles_updated += 1
    return tiles_updated


def colour_file(path: Path, minimum: float, maximum: float, scale: str) -> tuple[float, float]:
    if scale == "logarithmic":
        minimum, maximum = np.log10(1 + minimum), np.log10(1 + maximum)
    colours = (
        BATHYMETRY_COLOURS if scale == "bathymetry"
        else DIVERGING_COLOURS if scale == "diverging"
        else POWER_DENSITY_COLOURS if scale == "power-density"
        else SEQUENTIAL_COLOURS
    )
    with path.open("w", encoding="utf-8") as output:
        for value, colour in zip(np.linspace(minimum, maximum, len(colours)), colours):
            rgb = tuple(int(colour[index:index + 2], 16) for index in (1, 3, 5))
            output.write(f"{value:.10g} {rgb[0]} {rgb[1]} {rgb[2]}\n")
    return minimum, maximum


def write_domain_mask(
    path: Path, bounds: tuple[float, float, float, float], width: int, height: int,
) -> None:
    run(
        "gdal_rasterize", "-burn", "1", "-init", "0", "-te",
        *(f"{value:.8f}" for value in bounds), "-ts", str(width), str(height),
        "-ot", "Byte", "-of", "GTiff", str(DOMAIN_PATH), str(path),
    )


def render_layer(
    work_dir: Path, source: Path, spec: tuple[str, str, str, str, str, float, float, str],
    bounds: tuple[float, float, float, float], height: int, force: bool, *,
    domain_mask: Path, output: Path | None = None, width: int = RASTER_WIDTH,
    minimum_zoom: int = MIN_ZOOM, maximum_zoom: int = MAX_ZOOM,
    flow_arrows: list[tuple[float, float, float, float]] | None = None,
) -> None:
    slug, _, _, label, unit, minimum, maximum, scale = spec
    output = output or OUTPUT_DIR / slug
    if output.exists():
        if not force:
            print(f"Skipping existing web tiles: {output}")
            return
        shutil.rmtree(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    source_field = slug
    if scale == "logarithmic":
        source_field = f"{slug}_log"
        run(
            "ogr2ogr", "-f", "GPKG", str(work_dir / f"{slug}.gpkg"), str(source),
            "-sql", f"SELECT *, log(1 + \"{slug}\") AS \"{source_field}\" FROM faces",
        )
        source = work_dir / f"{slug}.gpkg"
    raw_raster = work_dir / f"{slug}.tif"
    coloured_raster = work_dir / f"{slug}-colours.tif"
    rgb_raster = work_dir / f"{slug}-rgb.tif"
    alpha_raster = work_dir / f"{slug}-alpha.tif"
    rgba_vrt = work_dir / f"{slug}-rgba.vrt"
    styled_raster = work_dir / f"{slug}-colour.tif"
    colour_map = work_dir / f"{slug}.txt"
    display_minimum, display_maximum = colour_file(colour_map, minimum, maximum, scale)
    run(
        "gdal_rasterize", "-a", source_field, "-where", "wet = 1",
        "-init", str(NODATA_VALUE), "-a_nodata", str(NODATA_VALUE), "-te",
        *(f"{value:.8f}" for value in bounds), "-ts", str(width), str(height),
        "-ot", "Float32", "-of", "GTiff", str(source), str(raw_raster),
    )
    run("gdaldem", "color-relief", str(raw_raster), str(colour_map), str(coloured_raster), "-alpha")
    run(
        "gdal_calc.py", "-A", str(raw_raster), "-B", str(domain_mask),
        "--calc", f"255*(A!={NODATA_VALUE})*(B!=0)",
        "--type=Byte", "--NoDataValue=0", "--overwrite", "--outfile", str(alpha_raster),
    )
    run(
        "gdal_translate", "-b", "1", "-b", "2", "-b", "3",
        str(coloured_raster), str(rgb_raster),
    )
    run("gdalbuildvrt", "-separate", str(rgba_vrt), str(rgb_raster), str(alpha_raster))
    run("gdal_translate", str(rgba_vrt), str(styled_raster))
    projected_raster = work_dir / f"{slug}-3857.tif"
    run(
        "gdalwarp", "-overwrite", "-t_srs", "EPSG:3857", "-r", "bilinear", "-srcalpha",
        "-dstalpha", "-co", "TILED=YES", "-co", "COMPRESS=DEFLATE",
        str(styled_raster), str(projected_raster),
    )
    run(
        "gdal2tiles.py", "--profile=mercator", "--xyz", "--webviewer=none",
        "--zoom", f"{minimum_zoom}-{maximum_zoom}", "--processes=4", "--exclude",
        "--tiledriver=WEBP", "--webp-quality=85",
        str(projected_raster), str(output),
    )
    if flow_arrows is not None:
        tiles_updated = bake_flow_arrows(
            output, flow_arrows, minimum_zoom, maximum_zoom,
        )
        print(f"Baked arrows into {tiles_updated} tiles: {slug}")


def export_tidal_sites(model_bounds: tuple[float, float, float, float]) -> None:
    if not SITES_PATH.is_file():
        raise FileNotFoundError(f"Tidal-sites source shapefile not found: {SITES_PATH}")
    west, south, east, north = model_bounds
    transformer = Transformer.from_crs("EPSG:32630", "EPSG:4326", always_xy=True)
    corners = [
        transformer.transform(x, y)
        for x in (west, east)
        for y in (south, north)
    ]
    longitude_bounds = min(x for x, _ in corners), max(x for x, _ in corners)
    latitude_bounds = min(y for _, y in corners), max(y for _, y in corners)
    geojson_path = OUTPUT_DIR / "tidal-sites.geojson"
    run(
        "ogr2ogr", "-f", "GeoJSON", str(geojson_path),
        "-spat",
        str(longitude_bounds[0]), str(latitude_bounds[0]),
        str(longitude_bounds[1]), str(latitude_bounds[1]),
        str(SITES_PATH),
        "-select", "Name_Prop,Name_Ten,Lease_Stat,Inf_Status,area_km_2",
    )
    sites = json.loads(geojson_path.read_text(encoding="utf-8"))
    if not sites["features"]:
        raise ValueError("No tidal-site polygons intersect the model domain")
    properties_by_name = {
        feature["properties"]["Name_Prop"]: feature["properties"]
        for feature in sites["features"]
    }
    missing_overrides = SITE_DISPLAY_OVERRIDES.keys() - properties_by_name.keys()
    if missing_overrides:
        raise ValueError(
            "Tidal-site source is missing properties for: "
            + ", ".join(sorted(missing_overrides))
        )
    for name, overrides in SITE_DISPLAY_OVERRIDES.items():
        properties_by_name[name].update(overrides)
    geojson = json.dumps(sites, ensure_ascii=False, separators=(",", ":"))
    geojson_path.write_text(geojson, encoding="utf-8")
    (OUTPUT_DIR / "tidal-sites.js").write_text(
        f"window.ORKNEY_TIDAL_SITES = {geojson};\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace existing tile directories",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="render high-resolution regional tiles instead of the standard tile set",
    )
    parser.add_argument(
        "--detail-region",
        choices=tuple(DETAIL_REGIONS),
        action="append",
        help="render only the named detail region (may be supplied more than once)",
    )
    parser.add_argument(
        "--detail-layer",
        choices=tuple(DETAIL_LAYER_SLUGS),
        action="append",
        help="render only the named visible layer (may be supplied more than once)",
    )
    parser.add_argument(
        "--layer",
        choices=tuple(spec[0] for spec in LAYER_SPECS),
        action="append",
        help="render only the named standard-resolution layer (may be supplied more than once)",
    )
    args = parser.parse_args()
    for command in (
        "ogr2ogr", "gdal_rasterize", "gdaldem", "gdal_calc.py", "gdal_translate",
        "gdalbuildvrt", "gdalwarp", "gdal2tiles.py", "convert",
    ):
        if shutil.which(command) is None:
            raise RuntimeError(f"Required GDAL command is unavailable: {command}")
    if not DOMAIN_PATH.is_file():
        raise FileNotFoundError(f"Domain polygon shapefile not found: {DOMAIN_PATH}")
    tables, x, y = read_layers()
    flow_arrows = sample_flow_arrows(tables, x, y)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bounds = (float(x.min()), float(y.min()), float(x.max()), float(y.max()))
    height = round(RASTER_WIDTH * (bounds[3] - bounds[1]) / (bounds[2] - bounds[0]))
    with tempfile.TemporaryDirectory(prefix="orkney-web-map-") as directory:
        work_dir = Path(directory)
        csv_path = work_dir / "faces.csv"
        gpkg_path = work_dir / "faces.gpkg"
        write_faces_csv(csv_path, tables, x, y)
        run(
            "ogr2ogr", "-f", "GPKG", str(gpkg_path), str(csv_path),
            "-oo", "GEOM_POSSIBLE_NAMES=WKT", "-a_srs", "EPSG:32630", "-nln", "faces",
        )
        if args.detail:
            regions = args.detail_region or tuple(DETAIL_REGIONS)
            layers = set(args.detail_layer or DETAIL_LAYER_SLUGS)
            for region in regions:
                detail_bounds = DETAIL_REGIONS[region]
                detail_height = round(
                    DETAIL_RASTER_WIDTH * (detail_bounds[3] - detail_bounds[1])
                    / (detail_bounds[2] - detail_bounds[0])
                )
                domain_mask = work_dir / f"{region}-domain-mask.tif"
                write_domain_mask(
                    domain_mask, detail_bounds, DETAIL_RASTER_WIDTH, detail_height,
                )
                for spec in LAYER_SPECS:
                    if spec[0] not in layers:
                        continue
                    render_layer(
                        work_dir, gpkg_path, spec, detail_bounds, detail_height, args.force,
                        domain_mask=domain_mask,
                        output=OUTPUT_DIR / "detail" / region / spec[0],
                        width=DETAIL_RASTER_WIDTH,
                        minimum_zoom=DETAIL_MIN_ZOOM,
                        maximum_zoom=DETAIL_MAX_ZOOM,
                        flow_arrows=flow_arrows.get(spec[0]),
                    )
        else:
            domain_mask = work_dir / "domain-mask.tif"
            write_domain_mask(domain_mask, bounds, RASTER_WIDTH, height)
            layers = set(args.layer or (spec[0] for spec in LAYER_SPECS))
            for spec in LAYER_SPECS:
                if spec[0] not in layers:
                    continue
                render_layer(
                    work_dir, gpkg_path, spec, bounds, height, args.force,
                    domain_mask=domain_mask,
                    flow_arrows=flow_arrows.get(spec[0]),
                )
    export_tidal_sites(bounds)

if __name__ == "__main__":
    main()
