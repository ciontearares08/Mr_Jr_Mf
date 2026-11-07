"""Map coordinates to cells in the DMI 10 km climate grid.

DMI names each cell after its south-west corner in EPSG:25832 (UTM zone 32N),
in units of 10 km: "10km_{northing}_{easting}".
"""

from pyproj import Transformer
from shapely.geometry.base import BaseGeometry

CELL_SIZE_M = 10_000

# Building a Transformer is slow, so we build it once at import time.
# always_xy=True keeps the axis order as (lon, lat) in and (easting, northing) out.
_WGS84_TO_UTM32 = Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True)


def cell_for(lat: float, lon: float) -> str:
    """Return the DMI 10 km grid cell ID that contains the WGS84 point."""
    easting, northing = _WGS84_TO_UTM32.transform(lon, lat)
    return f"10km_{int(northing // CELL_SIZE_M)}_{int(easting // CELL_SIZE_M)}"


def cell_for_geometry(geometry: BaseGeometry) -> str:
    """Return the cell of a point inside a WGS84 (lon, lat) geometry.

    The centroid of an L- or C-shaped field can fall outside the field, so we use
    representative_point(), which is always inside.
    """
    point = geometry.representative_point()
    return cell_for(lat=point.y, lon=point.x)
