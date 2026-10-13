#!/usr/bin/env python3
"""Validate the cached UGRID export through QGIS's MDAL provider."""

from __future__ import annotations

import argparse
from pathlib import Path

from qgis.core import QgsApplication, QgsMeshDatasetIndex, QgsMeshLayer

from export_ugrid_netcdf import SUMMARY_GROUP_NAMES, VECTOR_GROUP_NAMES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check UGRID mesh geometry and datasets using QGIS MDAL."
    )
    parser.add_argument(
        "mesh",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parent / "layers" / "orkney_case_study.nc",
        help="UGRID NetCDF mesh to validate",
    )
    parser.add_argument(
        "--bathymetry-only",
        action="store_true",
        help="expect the bathymetry-only export",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.mesh.is_file():
        raise FileNotFoundError(f"UGRID NetCDF file not found: {args.mesh}")

    application = QgsApplication([], False)
    application.initQgis()
    try:
        layer = QgsMeshLayer(str(args.mesh), args.mesh.stem, "mdal")
        if not layer.isValid():
            raise RuntimeError(f"QGIS could not load {args.mesh} through MDAL")

        provider = layer.dataProvider()
        if layer.crs().authid() != "EPSG:32630":
            raise RuntimeError(
                f"Expected CRS EPSG:32630, got {layer.crs().authid() or 'none'}"
            )
        expected_names = (
            {"Bathymetry"} if args.bathymetry_only else SUMMARY_GROUP_NAMES
        )
        group_count = provider.datasetGroupCount()
        group_names = {
            provider.datasetGroupMetadata(index).name()
            for index in range(group_count)
        }
        if layer.meshFaceCount() == 0:
            raise RuntimeError("MDAL loaded no mesh faces")
        if group_names != expected_names:
            missing = sorted(expected_names - group_names)
            unexpected = sorted(group_names - expected_names)
            raise RuntimeError(
                f"Unexpected dataset groups; missing={missing}, unexpected={unexpected}"
            )
        vector_status = {
            provider.datasetGroupMetadata(index).name(): provider.datasetGroupMetadata(index).isVector()
            for index in range(group_count)
        }
        expected_vectors = set() if args.bathymetry_only else set(VECTOR_GROUP_NAMES)
        wrong_vector_groups = sorted(
            name for name, is_vector in vector_status.items()
            if is_vector != (name in expected_vectors)
        )
        if wrong_vector_groups:
            raise RuntimeError(
                "Unexpected MDAL vector status for dataset groups: "
                f"{wrong_vector_groups}"
            )
        empty_groups = [
            provider.datasetGroupMetadata(index).name()
            for index in range(group_count)
            if provider.datasetCount(QgsMeshDatasetIndex(index, 0)) == 0
        ]
        if empty_groups:
            raise RuntimeError(f"Dataset groups with no datasets: {empty_groups}")

        print(
            f"Valid MDAL mesh: {layer.meshVertexCount()} vertices, "
            f"{layer.meshFaceCount()} faces, {group_count} dataset groups, "
            f"CRS {layer.crs().authid()}."
        )
    finally:
        application.exitQgis()


if __name__ == "__main__":
    main()
