from fastapi import APIRouter

router = APIRouter()

@router.get("/api/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}