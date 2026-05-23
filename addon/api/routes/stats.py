"""Stats and health endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from db.database import SessionLocal
from db.models import User
from core.stats_client import get_user_stats
from .api.auth import verify_admin
import subprocess

router = APIRouter(prefix="/api/v1", tags=["stats"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/health")
def health():
    try:
        subprocess.run(["systemctl", "is-active", "--quiet", "xray"], check=True)
        xray_running = True
    except:
        xray_running = False
    return {"status": "ok", "version": "1.0.0", "xray_running": xray_running}

@router.get("/stats", dependencies=[Depends(verify_admin)])
def global_stats(db: Session = Depends(get_db)):
    total = db.query(User).count()
    active = db.query(User).filter(User.status == "active").count()
    revoked = db.query(User).filter(User.status.in_(["revoked", "expired", "expired_quota"])).count()
    total_bytes = db.query(User).with_entities(User.bytes_used).all()
    total_used = sum(b[0] for b in total_bytes)
    try:
        subprocess.run(["systemctl", "is-active", "--quiet", "xray"], check=True)
        xray_status = "running"
    except:
        xray_status = "stopped"
    return {
        "total_users": total,
        "active_users": active,
        "revoked_users": revoked,
        "total_bytes_used": total_used,
        "xray_status": xray_status
    }

@router.get("/stats/users", dependencies=[Depends(verify_admin)])
def per_user_stats(db: Session = Depends(get_db)):
    users = db.query(User).filter(User.status == "active").all()
    result = []
    for u in users:
        try:
            stats = get_user_stats(u.email_tag)
        except:
            stats = {"uplink": 0, "downlink": 0, "total": 0}
        result.append({
            "username": u.username,
            "status": u.status,
            "uplink": stats["uplink"],
            "downlink": stats["downlink"],
            "total": stats["total"],
            "bytes_used": u.bytes_used,
            "data_cap_bytes": u.data_cap_bytes,
            "max_devices": u.max_devices
        })
    return result