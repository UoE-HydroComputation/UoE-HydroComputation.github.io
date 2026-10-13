"""Convert seabed-mounted ADCP and tide-gauge data into a map asset."""

import csv
import json
from pathlib import Path

from pyproj import Transformer


ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "_static" / "case-study" / "observation-sites.csv"
OUTPUT = ROOT / "_static" / "case-study" / "observation-sites.js"
TRANSFORMER = Transformer.from_crs("EPSG:32630", "EPSG:4326", always_xy=True)


def number(value):
    return float(value) if value else None


def main():
    with INPUT.open(newline="", encoding="utf-8") as source:
        rows = csv.DictReader(source)
        sites = []
        for row in rows:
            if row["Type"] not in {"SM", "Gauge"}:
                continue
            longitude = number(row["Lon"])
            latitude = number(row["Lat"])
            easting = number(row["x"])
            northing = number(row["y"])
            if longitude is None or latitude is None:
                longitude, latitude = TRANSFORMER.transform(easting, northing)

            properties = {
                key: value
                for key, value in row.items()
                if value and key not in {"Lat", "Lon", "x", "y"}
            }
            sites.append(
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "easting": easting,
                    "northing": northing,
                    "properties": properties,
                }
            )

    OUTPUT.write_text(
        f"window.ORKNEY_OBSERVATION_SITES = {json.dumps(sites, separators=(',', ':'))};\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
