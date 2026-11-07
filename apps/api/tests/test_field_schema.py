import pytest
from pydantic import ValidationError

from api.schemas.field import FieldCreate

SQUARE = [[10.38, 55.40], [10.40, 55.40], [10.40, 55.41], [10.38, 55.41]]
BOWTIE = [[10.38, 55.40], [10.40, 55.41], [10.40, 55.40], [10.38, 55.41]]
OFF_THE_MAP = [[0, 95], [1, 95], [1, 96], [0, 95]]
FLAT_LINE = [[10.38, 55.40], [10.39, 55.40], [10.40, 55.40], [10.38, 55.40]]


def _field(ring: list[list[float]]) -> dict:
    return {"name": "North field", "geometry": {"coordinates": [ring]}}


def test_accepts_a_valid_polygon() -> None:
    assert FieldCreate.model_validate(_field(SQUARE)).geometry.shape.is_valid


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "North field"},
        {"name": "North field", "geometry": {"coordinates": []}},
        _field(SQUARE[:2]),
        _field([]),
        _field(BOWTIE),
        _field(OFF_THE_MAP),
        _field([[10.38, float("nan")], *SQUARE[1:]]),
        _field(FLAT_LINE),
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
    ],
)
def test_rejects_a_bad_polygon(payload: dict) -> None:
    with pytest.raises(ValidationError):
        FieldCreate.model_validate(payload)


def test_the_error_names_the_real_problem() -> None:
    with pytest.raises(ValidationError, match="Self-intersection"):
        FieldCreate.model_validate(_field(BOWTIE))
