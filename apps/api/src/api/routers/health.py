from fastapi import APIRouter, FastAPI

router = APIRouter()
app = FastAPI()

@router.get("/api/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}

app.include_router(router)