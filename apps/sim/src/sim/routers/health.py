import os
import subprocess
from fastapi import APIRouter

router = APIRouter(prefix="/sim")

@router.get("/health")
def health_check():
    apsim_bin = os.getenv("APSIM", "/opt/apsim/Models")
    try:
        # Call the CLI to get the version
        result = subprocess.run([apsim_bin, "--version"], capture_output=True, text=True, check=True)
        apsim_version = result.stdout.strip()
    except Exception as e:
        apsim_version = f"unknown (Error: {e})"
        
    return {"status": "ok", "apsim_version": apsim_version}