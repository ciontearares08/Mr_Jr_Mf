import pytest
from pyproj import Transformer
from shapely.geometry import Polygon

from api.geometry import area_ha

_UTM32_TO_WGS84 = Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)


def _square_near_odense(side_m: float) -> Polygon:
    """Build a square with the given side in meters, as WGS84 (lon, lat) points."""
    easting, northing = 588_000, 6_140_000
    corners = [
        (easting, northing),
        (easting + side_m, northing),
        (easting + side_m, northing + side_m),
        (easting, northing + side_m),
    ]
    return Polygon([_UTM32_TO_WGS84.transform(x, y) for x, y in corners])


def test_a_100_m_square_is_one_hectare() -> None:
    # UTM scales lengths by up to 0.04 %, so allow 0.1 % on the area.
    assert area_ha(_square_near_odense(100)) == pytest.approx(1.0, rel=1e-3)


def test_area_does_not_depend_on_ring_direction() -> None:
    square = _square_near_odense(100)
    reversed_square = Polygon(list(square.exterior.coords)[::-1])
    assert area_ha(reversed_square) == pytest.approx(area_ha(square))


def test_a_hole_is_subtracted_whatever_its_direction() -> None:
    outer = _square_near_odense(200)  # 4 ha
    inner = _square_near_odense(100)  # 1 ha, shares the south-west corner
    hole = [(x + 1e-4, y + 1e-4) for x, y in inner.exterior.coords]
    # Both rings run the same way, which Geod alone would add together.
    same_direction = Polygon(outer.exterior.coords, [hole])
    assert area_ha(same_direction) == pytest.approx(3.0, rel=1e-2)
