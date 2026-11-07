import subprocess

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from sim.apsim import apsim_models_path

router = APIRouter(prefix="/sim")


@router.get("/health")
def health_check():
    try:
        result = subprocess.run(
            [apsim_models_path(), "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "apsim_version": f"unknown (Error: {e})"},
        )

    return {"status": "ok", "apsim_version": result.stdout.strip()}
