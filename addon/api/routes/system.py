import sys, subprocess, json
sys.path.insert(0, '/opt/xhttp-manager/addon')
from fastapi import APIRouter, Depends, HTTPException
from api.auth import verify_admin

router = APIRouter(prefix="/api/v1/system", tags=["system"])

@router.post("/reload", dependencies=[Depends(verify_admin)])
def reload_xray():
    try:
        subprocess.run(["systemctl", "restart", "xray"], check=True)
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

@router.get("/status", dependencies=[Depends(verify_admin)])
def system_status():
    import os
    status = {
        "xray_running": False,
        "api_running": False,
        "enforcer_timer": False,
        "db_size": 0
    }
    try:
        subprocess.run(["systemctl", "is-active", "--quiet", "xray"], check=True)
        status["xray_running"] = True
    except:
        pass
    try:
        subprocess.run(["systemctl", "is-active", "--quiet", "xhttp-manager"], check=True)
        status["api_running"] = True
    except:
        pass
    try:
        subprocess.run(["systemctl", "is-active", "--quiet", "xhttp-enforcer.timer"], check=True)
        status["enforcer_timer"] = True
    except:
        pass
    if os.path.exists("/var/lib/xhttp-manager/db.sqlite"):
        status["db_size"] = os.path.getsize("/var/lib/xhttp-manager/db.sqlite")
    return status
