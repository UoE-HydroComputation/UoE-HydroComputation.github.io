# QGIS case-study layers

`prepare_qgis_layers.py` is the **only** case-study step that reads and
processes transient velocities from `results.h5`. It creates tab-delimited,
node-based cache tables in `case_study/layers/`; `export_ugrid_netcdf.py` and
`validate_qgis_mesh.py` use only those tables plus static mesh topology.

## Workflow

Install the processing dependencies, then run this expensive command once from
the repository root (it leaves `results.h5` unchanged):

```bash
python -m pip install -r case_study/requirements.txt
python case_study/prepare_qgis_layers.py
```

The default selected period is the first 14.765 days (`0.5 * 29.53`) saved in
the source. `--start` and `--days` select another fully-covered period; use
`--all-times` for the complete source range. Flood and ebb are classified at
the node nearest `(492329, 6502216)` from headings nearest 110° and 270°,
respectively (flow direction clockwise from north; ties are ebb). That one
classification applies at every mesh node.

Package the resulting cache without repeating transient processing:

```bash
python case_study/export_ugrid_netcdf.py
QT_QPA_PLATFORM=offscreen /usr/bin/python3 case_study/validate_qgis_mesh.py
```

To add only the neap peak flood/ebb speed fields to an existing cache, without
rebuilding other summaries or recalculating vorticity, run
`python case_study/prepare_qgis_layers.py --neap-peaks-only`.

Load `case_study/layers/orkney_case_study.nc` in QGIS using **Layer → Add Layer
→ Add Mesh Layer** so that the MDAL provider is used. The optional
`--bathymetry-only` exporter creates a static-only mesh.

## Cached fields and definitions

Every `.txt` table has `x`, `y` (metres, EPSG:32630) and the following named
value columns. All temporal mean speeds are means of instantaneous
`hypot(u, v)`, not magnitudes of averaged components.

* `bathymetry_m` — bathymetry (m).
* `mean_speed_m_s`, `mean_direction_deg`, flood/ebb speed, u, v and heading,
  and all three kinetic-power-density fields retain the existing selected-period
  summaries. Power density is the mean of `0.5 * 1025 * speed³` (W/m²).
* `residual_current_speed_m_s`, `residual_current_u_m_s`, and
  `residual_current_v_m_s` — magnitude and components of the selected-period
  mean velocity (the residual current).
* `flood_ebb_asymmetry` — `(mean flood speed - mean ebb speed) / (mean flood
  speed + mean ebb speed)`, a dimensionless value from -1 to +1. Zero means
  equal flood and ebb speeds; values are undefined where both are zero.
* `spring_mean_speed_m_s`, `spring_mean_flood_speed_m_s`,
  `spring_mean_ebb_speed_m_s`, and the corresponding `neap_*` fields —
  temporal means in their respective tidal-day window. Spring and neap are
  24.84-hour windows centred on the highest and lowest local maxima,
  respectively, of reference-node speed; each window must be fully contained
  in the selected period.
* `spring_peak_flood_speed_m_s`, `spring_peak_ebb_speed_m_s` — instantaneous
  speed at every node at a common timestamp within the spring window, selected
  separately for flood and ebb as the timestamp with the highest reference-node
  speed in that flow direction. Flood and ebb are classified from flow
  direction in the Inner Sound.
* `neap_peak_flood_speed_m_s`, `neap_peak_ebb_speed_m_s` — the corresponding
  common-timestamp peak speeds within the neap tidal-day window.
* `peak_flood_vorticity_s_1`, `peak_ebb_vorticity_s_1` — at each node, signed
  `dv/dx - du/dy` with the greatest absolute magnitude across all timesteps
  classified as flood or ebb, respectively, in the selected period. Each
  node's extremum can occur at a different time.
The UGRID export has one scalar MDAL group for each scalar field. Its only
vector groups are **Residual current velocity**, **Mean flood velocity**, and
**Mean ebb velocity**, each formed from recognized eastward/northward u/v
pairs. There is deliberately no **Mean velocity** vector group or overall
mean u/v export.

Tables retain eight decimal places. The NetCDF exporter rounds node data to
four decimal places and writes 32-bit floats by default; coordinates and mesh
connectivity retain their source precision. `layer_metadata.txt` records
source/selection coverage, tidal-day centres and peak timestamps,
classification counts and the reference node.

## Website map layers

`render_web_map_layers.py` derives local web-map tiles for configured display
layers from the ignored cache tables and static mesh. It paints direction
arrows directly into the mean flood, mean ebb and residual-current speed tile
images; arrows show the mean-vector direction and are omitted below 0.1 m/s. It also
converts the Crown Estate Scotland tidal-sites shapefile to a GeoJSON overlay,
retaining only the tenant, lease, project phase, capacity and site-name fields.
The exported website attributes include explicit display overrides for the
Orkney sites whose tenant, lease and project phase details were updated.
Flow direction is shown by arrows embedded in the speed-layer images, rather
than as a separate heading colour layer or browser overlay.
It does not modify the cache tables, NetCDF or HDF5 source:

```bash
python case_study/render_web_map_layers.py
```

It requires the GDAL command-line tools (`ogr2ogr`, `gdal_rasterize`,
`gdaldem`, `gdalwarp`, and `gdal2tiles.py`), ImageMagick's `convert`, and the
Python requirements above. Existing layer tile directories are retained when the renderer is rerun, so it
can generate newly added fields without re-rendering unchanged layers. The
`--force` option replaces existing tile directories when the rendering logic changes.
Use `--layer <name>` to replace selected standard-resolution layers. The compact
Pentland Firth and Westray--Stronsay detail pyramids are generated with
`--detail`; `--detail-region <name>` and `--detail-layer <name>` limit that
work to named regions or displayed layers. land and out-of-domain pixels are emitted as transparent tiles so the map
background is visible in those locations. The renderer clips every tile to
the filled EPSG:32630 domain polygon in `OrkneysAdjoint-v0.shp`, including its
coastline and island holes. This shapefile is required for tile generation;
the model mesh remains the source of the rendered values.
generated Web Mercator WebP tiles are published in `_static/case-study/`; they
are visual renderings for the website, not analysis data. Flood/ebb vorticity
tiles visualize each node's signed temporal extreme,
which may occur at different timesteps across nodes. The browser map uses
locally bundled Leaflet 1.9.4 assets and does not
request third-party basemap tiles. Vorticity tiles saturate at ±0.05 s⁻¹, and
the website colorbar marks out-of-range values with inequalities. The sites source is
`Tidal (Crown Estate Scotland)`, © Crown Estate Scotland 2021, obtained from
the linked ArcGIS service in `lease-sites/CES-TidalSites2025.qmd`.
Spring and neap mean/peak speed layers are grouped under **Spring tide** and
**Neap tide** in the layer menu. Observational overlays start switched off.
Interpolated bathymetry uses a shallow-turquoise to deep-navy colour scale.
