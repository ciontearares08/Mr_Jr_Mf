import pytest
from pydantic import ValidationError

from api.schemas.field import FieldCreate

SQUARE = [[10.38, 55.40], [10.40, 55.40], [10.40, 55.41], [10.38, 55.41]]
BOWTIE = [[10.38, 55.40], [10.40, 55.41], [10.40, 55.40], [10.38, 55.41]]
OFF_THE_MAP = [[0, 95], [1, 95], [1, 96], [0, 95]]
IN_SPAIN = [[-3.70, 40.41], [-3.69, 40.41], [-3.69, 40.42], [-3.70, 40.41]]
FLAT_LINE = [[10.38, 55.40], [10.39, 55.40], [10.40, 55.40], [10.38, 55.40]]


def _field(ring: list[list[float]]) -> dict:
    return {
        "name": "North field",
        "geometry": {"coordinates": [ring]},
        "sowing_date": "2026-09-20",
    }


def _sowing(**sowing: object) -> dict:
    """A valid field with only the given sowing values."""
    field = _field(SQUARE)
    del field["sowing_date"]
    return field | sowing


def test_accepts_a_valid_polygon() -> None:
    assert FieldCreate.model_validate(_field(SQUARE)).geometry.shape.is_valid


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "North field", "sowing_date": "2026-09-20"},
        {
            "name": "North field",
            "geometry": {"coordinates": []},
            "sowing_date": "2026-09-20",
        },
        _field(SQUARE[:2]),
        _field([]),
        _field(BOWTIE),
        _field(OFF_THE_MAP),
        _field([[10.38, float("nan")], *SQUARE[1:]]),
        _field(FLAT_LINE),
        _field(IN_SPAIN),
    ],
    ids=[
        "missing",
        "no rings",
        "too few points",
        "empty ring",
        "self-intersecting",
        "latitude out of range",
        "not a number",
        "no area",
        "outside the DMI grid",
    ],
)
def test_rejects_a_bad_polygon(payload: dict) -> None:
    with pytest.raises(ValidationError):
        FieldCreate.model_validate(payload)


def test_the_error_names_the_real_problem() -> None:
    with pytest.raises(ValidationError, match="Self-intersection"):
        FieldCreate.model_validate(_field(BOWTIE))


@pytest.mark.parametrize(
    "extra_values", [[0], [0, 0]], ids=["altitude", "altitude and measure"]
)
def test_accepts_points_with_extra_values(extra_values: list[float]) -> None:
    square_with_extra_values = [[lon, lat, *extra_values] for lon, lat in SQUARE]
    field = FieldCreate.model_validate(_field(square_with_extra_values))
    assert not field.geometry.shape.has_z


def test_the_error_says_the_field_is_outside_denmark() -> None:
    with pytest.raises(ValidationError, match="outside Denmark"):
        FieldCreate.model_validate(_field(IN_SPAIN))


WINDOW = {"start": "2026-09-15", "end": "2026-10-05"}


@pytest.mark.parametrize(
    "sowing",
    [{"sowing_date": "2026-09-20"}, {"sowing_window": WINDOW}],
    ids=["date", "window"],
)
def test_accepts_a_sowing_date_or_window(sowing: dict) -> None:
    FieldCreate.model_validate(_sowing(**sowing))


@pytest.mark.parametrize(
    ("sowing", "message"),
    [
        ({}, "Give a sowing date or a sowing window"),
        ({"sowing_date": "2026-09-20", "sowing_window": WINDOW}, "not both"),
        (
            {"sowing_window": {"start": "2026-10-05", "end": "2026-09-15"}},
            "must start before it ends",
        ),
        ({"sowing_window": {"start": "2026-09-15"}}, "end"),
    ],
    ids=["none", "both", "reversed window", "window without end"],
)
def test_rejects_bad_sowing_data(sowing: dict, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        FieldCreate.model_validate(_sowing(**sowing))
