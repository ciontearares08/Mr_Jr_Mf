import pytest
from shapely.geometry import Polygon

from api.weather.grid import (
    cell_centre,
    cell_for,
    cell_for_geometry,
    is_inside_dmi_grid,
)


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


@pytest.mark.parametrize("cell_id", ["10km_632_55", "10km_614_58", "10km_617_72"])
def test_cell_centre_lies_in_its_own_cell(cell_id: str) -> None:
    assert cell_for(*cell_centre(cell_id)) == cell_id


def test_cell_centre_of_the_copenhagen_cell() -> None:
    lat, lon = cell_centre("10km_617_72")
    assert (round(lat, 2), round(lon, 2)) == (55.67, 12.58)


@pytest.mark.parametrize("cell_id", ["", "10km_617", "1km_617_72", "10km_a_72"])
def test_cell_centre_rejects_a_bad_cell_id(cell_id: str) -> None:
    with pytest.raises(ValueError, match="not a DMI 10 km cell ID"):
        cell_centre(cell_id)


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


def small_field_at(lon: float, lat: float) -> Polygon:
    """A field of about 100 m by 100 m with its south-west corner at the point."""
    return Polygon(
        [(lon, lat), (lon + 0.001, lat), (lon + 0.001, lat + 0.001), (lon, lat + 0.001)]
    )


@pytest.mark.parametrize(
    ("lon", "lat"),
    [
        (10.39, 55.40),  # Odense
        (12.57, 55.68),  # Copenhagen
        (10.59, 57.72),  # Skagen
        (8.45, 55.47),  # Esbjerg
        (8.86, 54.93),  # Tønder, at the German border
        (9.358, 54.826),  # Padborg, at the German border
        (9.317, 54.808),  # Frøslev, at the German border
        (9.47, 54.845),  # Kollund, on Flensburg Fjord
        (11.93, 54.57),  # Gedser
        (12.61, 56.03),  # Helsingør
        (11.55, 56.70),  # Anholt
        (14.70, 55.10),  # Rønne, Bornholm
    ],
)
def test_a_field_in_denmark_is_inside_the_dmi_grid(lon: float, lat: float) -> None:
    assert is_inside_dmi_grid(small_field_at(lon, lat))


@pytest.mark.parametrize(
    ("lon", "lat"),
    [
        (-3.70, 40.41),  # Madrid
        (13.00, 55.60),  # Malmö, Sweden
        (11.97, 57.71),  # Gothenburg, Sweden
        (12.86, 56.67),  # Halmstad, Sweden
        (12.70, 56.05),  # Helsingborg, Sweden
        (13.82, 55.43),  # Ystad, Sweden
        (9.43, 54.78),  # Flensburg, Germany
        (9.39, 54.795),  # Harrislee, Germany
        (9.55, 54.833),  # Glücksburg, Germany
        (9.58, 54.86),  # Holnis, Germany
        (8.32, 54.95),  # Sylt, Germany
        (11.15, 54.48),  # Fehmarn, Germany
    ],
)
def test_a_field_outside_denmark_is_outside_the_dmi_grid(
    lon: float, lat: float
) -> None:
    assert not is_inside_dmi_grid(small_field_at(lon, lat))
