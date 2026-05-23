"""System management routes."""
from fastapi import APIRouter, Depends, HTTPException
from .api.auth import verify_admin
import subprocess
import json

router = APIRouter(prefix="/api/v1/system", tags=["system"])

@router.post("/reload", dependencies=[Depends(verify_admin)])
def reload_xray():
    try:
        subprocess.run(["systemctl", "reload", "xray"], check=True)
        return {"status": "reloaded"}
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, detail=f"Reload failed: {e}")

@router.get("/deployment", dependencies=[Depends(verify_admin)])
def deployment_info():
    try:
        with open("/var/lib/xhttp-manager/deployment.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(404, detail="Deployment info not found")