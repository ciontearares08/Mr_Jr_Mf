from fastapi import APIRouter

router = APIRouter()


@router.get("/sim/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "awesome"}
