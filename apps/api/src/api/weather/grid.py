"""Map coordinates to cells in the DMI 10 km climate grid.

DMI names each cell after its south-west corner in EPSG:25832 (UTM zone 32N),
in units of 10 km: "10km_{northing}_{easting}".
"""

from pyproj import Transformer
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

CELL_SIZE_M = 10_000

# DMI computes the grid only for Denmark. These (lon, lat) outlines go around
# Denmark and Bornholm. At sea they follow the middle line between Denmark and
# its neighbors, and on land the German border, to within a few km. A simple
# box is not enough, because it also covers Skåne and Halland in Sweden.
DENMARK_WITHOUT_BORNHOLM = Polygon(
    [
        (7.90, 55.10),  # North Sea, between Rømø and Sylt (Germany)
        (8.55, 55.06),
        (8.65, 54.91),  # Land border with Germany
        (8.92, 54.90),  # South of Tønder
        (9.12, 54.87),
        (9.25, 54.84),
        (9.32, 54.80),  # South of Frøslev and Padborg
        (9.38, 54.80),
        (9.42, 54.82),  # Flensburg Fjord, middle line
        (9.50, 54.835),  # Between Kollund and Glücksburg (Germany)
        (9.58, 54.873),  # Between Rinkenæs and Holnis (Germany)
        (9.70, 54.845),
        (9.95, 54.80),  # Fjord mouth, south of Kegnæs
        (10.10, 54.72),  # Baltic Sea, south of Als, Ærø and Langeland
        (11.00, 54.58),  # Fehmarn Belt, north of Fehmarn (Germany)
        (12.10, 54.48),  # South of Gedser
        (12.65, 54.75),  # West of Rügen (Germany)
        (12.62, 55.33),  # Øresund, between Stevns and Falsterbo (Sweden)
        (12.85, 55.62),  # Between Saltholm and Malmö (Sweden)
        (12.62, 55.90),  # West of Ven (Sweden)
        (12.66, 56.04),  # Between Helsingør and Helsingborg (Sweden)
        (12.35, 56.22),  # Kattegat, west of Kullen (Sweden)
        (12.00, 56.45),
        (11.95, 56.85),  # East of Anholt
        (11.60, 57.30),  # East of Læsø
        (11.15, 57.80),  # West of Gothenburg (Sweden)
        (10.20, 58.00),  # Skagerrak, north of Skagen
        (7.90, 57.40),  # North Sea, west of Hanstholm
    ]
)
BORNHOLM = Polygon([(14.60, 54.95), (15.25, 54.95), (15.25, 55.35), (14.60, 55.35)])
DMI_GRID_AREA = MultiPolygon([DENMARK_WITHOUT_BORNHOLM, BORNHOLM])

# Building a Transformer is slow, so we build it once at import time.
# always_xy=True keeps the axis order as (lon, lat) in and (easting, northing) out.
WGS84_TO_UTM32 = Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True)


def cell_for(lat: float, lon: float) -> str:
    """Return the DMI 10 km grid cell ID that contains the WGS84 point."""
    easting, northing = WGS84_TO_UTM32.transform(lon, lat)
    return f"10km_{int(northing // CELL_SIZE_M)}_{int(easting // CELL_SIZE_M)}"


def cell_centre(cell_id: str) -> tuple[float, float]:
    """Return the (lat, lon) in WGS84 of the middle of a cell, the inverse of cell_for."""
    try:
        prefix, northing, easting = cell_id.split("_")
        if prefix != "10km":
            raise ValueError
        centre_northing = (int(northing) + 0.5) * CELL_SIZE_M
        centre_easting = (int(easting) + 0.5) * CELL_SIZE_M
    except ValueError:
        raise ValueError(f"{cell_id!r} is not a DMI 10 km cell ID") from None
    lon, lat = WGS84_TO_UTM32.transform(
        centre_easting, centre_northing, direction="INVERSE"
    )
    return lat, lon


def is_inside_dmi_grid(geometry: BaseGeometry) -> bool:
    """Return True when the whole WGS84 (lon, lat) geometry is in the DMI grid area."""
    return DMI_GRID_AREA.covers(geometry)


def cell_for_geometry(geometry: BaseGeometry) -> str:
    """Return the cell of a point inside a WGS84 (lon, lat) geometry.

    The centroid of an L- or C-shaped field can fall outside the field, so we use
    representative_point(), which is always inside.
    """
    point = geometry.representative_point()
    return cell_for(lat=point.y, lon=point.x)
