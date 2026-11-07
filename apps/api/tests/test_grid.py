import pytest
from shapely.geometry import Polygon

from api.weather.grid import cell_for, cell_for_geometry


@pytest.mark.parametrize(
    ("town", "lat", "lon", "expected_cell"),
    [
        ("Aalborg", 57.0488, 9.9217, "10km_632_55"),
        ("Odense", 55.4038, 10.3883, "10km_614_58"),
    ],
)
def test_cell_for_known_towns(
    town: str, lat: float, lon: float, expected_cell: str
) -> None:
    assert cell_for(lat, lon) == expected_cell, town


def test_points_in_the_same_cell_share_an_id() -> None:
    assert cell_for(57.0488, 9.9217) == cell_for(57.0490, 9.9220)


def test_cell_for_geometry_of_a_square() -> None:
    # A small square around the centre of Odense, as (lon, lat) pairs.
    field = Polygon([(10.38, 55.40), (10.40, 55.40), (10.40, 55.41), (10.38, 55.41)])
    assert cell_for_geometry(field) == cell_for(lat=55.405, lon=10.39)


def test_cell_for_geometry_uses_a_point_inside_the_field() -> None:
    # A thin C shape: its centroid is in the empty middle, outside the field.
    c_shape = Polygon(
        [(0, 0), (10, 0), (10, 1), (1, 1), (1, 9), (10, 9), (10, 10), (0, 10)]
    )
    assert not c_shape.contains(c_shape.centroid)
    assert c_shape.contains(c_shape.representative_point())
