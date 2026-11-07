"""Measurements on WGS84 (lon, lat) geometries."""

from pyproj import Geod
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

SQUARE_METERS_PER_HECTARE = 10_000

_WGS84 = Geod(ellps="WGS84")


def area_ha(polygon: Polygon) -> float:
    """Return the area of a WGS84 polygon in hectares, measured on the ellipsoid."""
    # Geod adds the signed ring areas, so holes only subtract when they run
    # opposite to the outer ring. orient() makes the outer ring counter-clockwise
    # and the holes clockwise, which gives a positive area minus the holes.
    area_m2, _perimeter = _WGS84.geometry_area_perimeter(orient(polygon))
    return area_m2 / SQUARE_METERS_PER_HECTARE
