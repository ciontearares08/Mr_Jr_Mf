from fastapi import APIRouter

from sim.schemas import SimulateRequest, SimulateResponse
from sim.simulate import run_members

router = APIRouter(prefix="/sim")


@router.post("/simulate")
def simulate(request: SimulateRequest) -> SimulateResponse:
    """Run APSIM once per member and return the daily rows of each run.

    A member that fails gets status "failed" and an error message; the other
    members are not affected, and the response is still 200.
    """
    return SimulateResponse(members=run_members(request))
