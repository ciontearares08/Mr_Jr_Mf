from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[4] / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers.auth import router as auth_router
from api.routers.fields import router as fields_router
from api.routers.health import router as health_router
from api.routers.stubs import router as stubs_router

app = FastAPI(title="Agricultural Data API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(fields_router)
app.include_router(auth_router)
app.include_router(stubs_router)
