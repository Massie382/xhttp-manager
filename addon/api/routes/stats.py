import sys, subprocess
sys.path.insert(0, '/opt/xhttp-manager/addon')
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from db.database import SessionLocal
from db.models import User
from core.stats_client import get_user_stats, get_all_user_stats
from api.auth import verify_admin

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
    total_bytes = sum(b[0] for b in db.query(User.bytes_used).all())
    try:
        subprocess.run(["systemctl", "is-active", "--quiet", "xray"], check=True)
        xray_status = "running"
    except:
        xray_status = "stopped"
    return {
        "total_users": total,
        "active_users": active,
        "revoked_users": revoked,
        "total_bytes_used": total_bytes,
        "xray_status": xray_status
    }

@router.get("/stats/users", dependencies=[Depends(verify_admin)])
def per_user_stats(username: Optional[str] = None, db: Session = Depends(get_db)):
    if username:
        users = db.query(User).filter(User.username == username).all()
    else:
        users = db.query(User).filter(User.status == "active").all()
    
    if not users:
        return []
    
    emails = [u.email_tag for u in users]
    live_stats = {s['email']: s for s in get_all_user_stats(emails)}
    
    result = []
    for u in users:
        stats = live_stats.get(u.email_tag, {"uplink": 0, "downlink": 0, "total": 0})
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
    
    if username and result:
        return result[0]
    return result

@router.get("/export", dependencies=[Depends(verify_admin)])
def export_users(format: str = "csv", db: Session = Depends(get_db)):
    users = db.query(User).filter(User.status == "active").all()
    if format == "csv":
        csv = "username,uuid,expiry_at,data_cap_gb,bytes_used_gb,max_devices,status,vless_uri\n"
        for u in users:
            cap_gb = f"{u.data_cap_bytes / (1024**3):.2f}" if u.data_cap_bytes else ""
            used_gb = f"{u.bytes_used / (1024**3):.2f}" if u.bytes_used else "0.00"
            expiry = time.strftime('%Y-%m-%d', time.gmtime(u.expiry_at)) if u.expiry_at else ""
            csv += f"{u.username},{u.uuid},{expiry},{cap_gb},{used_gb},{u.max_devices or ''},{u.status},{u.vless_uri}\n"
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=csv, media_type="text/csv")
    elif format == "json":
        return [user_to_response(u) for u in users]
    else:
        raise HTTPException(400, detail="Format not supported")
