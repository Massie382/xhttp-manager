"""User management routes."""
import time
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from db.database import SessionLocal
from db.models import User, AuditLog
from core.crypto import generate_uuid
from core.config_manager import add_client, remove_client
from core.uri_builder import build_vless_uri
from .api.auth import verify_admin
from ..models.schemas import (
    UserCreate, UserUpdate, UserExtend, BulkUserCreate,
    UserResponse, UserListResponse
)
import json

router = APIRouter(prefix="/api/v1/users", tags=["users"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        uuid=user.uuid,
        status=user.status,
        created_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(user.created_at)),
        expiry_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(user.expiry_at)) if user.expiry_at else None,
        data_cap_bytes=user.data_cap_bytes,
        bytes_used=user.bytes_used,
        max_devices=user.max_devices,
        vless_uri=user.vless_uri,
        note=user.note
    )

@router.post("", response_model=UserResponse, status_code=201, dependencies=[Depends(verify_admin)])
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(409, detail="Username already exists")
    uuid = generate_uuid()
    email = f"{payload.username}@xhttp"
    now = int(time.time())
    expiry = now + payload.expiry_days * 86400 if payload.expiry_days else None
    data_cap = int(payload.data_cap_gb * 1024**3) if payload.data_cap_gb else None
    uri = build_vless_uri(uuid, payload.username)
    user = User(
        username=payload.username,
        uuid=uuid,
        email_tag=email,
        status="active",
        created_at=now,
        expiry_at=expiry,
        data_cap_bytes=data_cap,
        bytes_used=0,
        max_devices=payload.max_devices,
        note=payload.note,
        vless_uri=uri
    )
    db.add(user)
    db.commit()
    add_client(uuid, email)
    log = AuditLog(ts=now, action="create", username=payload.username, actor="admin",
                   detail=json.dumps(payload.dict()))
    db.add(log)
    db.commit()
    db.refresh(user)
    return user_to_response(user)

@router.get("", response_model=UserListResponse, dependencies=[Depends(verify_admin)])
def list_users(status: Optional[str] = Query(None), limit: int = Query(100, le=1000), offset: int = Query(0),
               db: Session = Depends(get_db)):
    query = db.query(User)
    if status:
        query = query.filter(User.status == status)
    total = query.count()
    users = query.offset(offset).limit(limit).all()
    return UserListResponse(total=total, users=[user_to_response(u) for u in users])

@router.get("/{username}", response_model=UserResponse, dependencies=[Depends(verify_admin)])
def get_user(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, detail="User not found")
    return user_to_response(user)

@router.delete("/{username}", dependencies=[Depends(verify_admin)])
def revoke_user(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, detail="User not found")
    if user.status == "revoked":
        raise HTTPException(409, detail="User already revoked")
    user.status = "revoked"
    db.commit()
    remove_client(user.uuid)
    log = AuditLog(ts=int(time.time()), action="revoke", username=username, actor="admin")
    db.add(log)
    db.commit()
    return {"message": f"User {username} revoked"}

@router.patch("/{username}", response_model=UserResponse, dependencies=[Depends(verify_admin)])
def update_limits(username: str, payload: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, detail="User not found")
    if payload.expiry_days is not None:
        user.expiry_at = int(time.time()) + payload.expiry_days * 86400
    if payload.data_cap_gb is not None:
        user.data_cap_bytes = int(payload.data_cap_gb * 1024**3)
    if payload.max_devices is not None:
        user.max_devices = payload.max_devices
    if payload.note is not None:
        user.note = payload.note
    if payload.reset_usage:
        user.bytes_used = 0
    db.commit()
    log = AuditLog(ts=int(time.time()), action="set_limits", username=username, actor="admin",
                   detail=json.dumps(payload.dict(exclude_unset=True)))
    db.add(log)
    db.commit()
    db.refresh(user)
    return user_to_response(user)

@router.post("/{username}/extend", dependencies=[Depends(verify_admin)])
def extend_user(username: str, payload: UserExtend, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, detail="User not found")
    prev = user.expiry_at
    new_expiry = (prev or int(time.time())) + payload.days * 86400
    user.expiry_at = new_expiry
    db.commit()
    log = AuditLog(ts=int(time.time()), action="extend", username=username, actor="admin",
                   detail=json.dumps({"days": payload.days, "previous_expiry": prev}))
    db.add(log)
    db.commit()
    return {
        "username": username,
        "previous_expiry": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(prev)) if prev else None,
        "new_expiry": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(new_expiry))
    }

@router.post("/{username}/suspend", dependencies=[Depends(verify_admin)])
def suspend_user(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, detail="User not found")
    if user.status != "active":
        raise HTTPException(409, detail=f"Cannot suspend user with status {user.status}")
    user.status = "suspended"
    db.commit()
    remove_client(user.uuid)
    log = AuditLog(ts=int(time.time()), action="suspend", username=username, actor="admin")
    db.add(log)
    db.commit()
    return {"message": f"User {username} suspended"}

@router.post("/{username}/unsuspend", dependencies=[Depends(verify_admin)])
def unsuspend_user(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, detail="User not found")
    if user.status != "suspended":
        raise HTTPException(409, detail="User is not suspended")
    user.status = "active"
    db.commit()
    add_client(user.uuid, user.email_tag)
    log = AuditLog(ts=int(time.time()), action="unsuspend", username=username, actor="admin")
    db.add(log)
    db.commit()
    return {"message": f"User {username} unsuspended"}

@router.post("/bulk", dependencies=[Depends(verify_admin)])
def bulk_create(payload: BulkUserCreate, db: Session = Depends(get_db)):
    results = []
    created = 0
    for user_data in payload.users:
        try:
            if db.query(User).filter(User.username == user_data.username).first():
                results.append({"username": user_data.username, "error": "exists"})
                continue
            uuid = generate_uuid()
            email = f"{user_data.username}@xhttp"
            now = int(time.time())
            expiry = now + user_data.expiry_days * 86400 if user_data.expiry_days else None
            cap = int(user_data.data_cap_gb * 1024**3) if user_data.data_cap_gb else None
            uri = build_vless_uri(uuid, user_data.username)
            user = User(
                username=user_data.username,
                uuid=uuid,
                email_tag=email,
                status="active",
                created_at=now,
                expiry_at=expiry,
                data_cap_bytes=cap,
                bytes_used=0,
                max_devices=user_data.max_devices,
                note=user_data.note,
                vless_uri=uri
            )
            db.add(user)
            db.commit()
            add_client(uuid, email)
            log = AuditLog(ts=now, action="create", username=user_data.username, actor="admin",
                           detail=json.dumps(user_data.dict()))
            db.add(log)
            db.commit()
            results.append({"username": user_data.username, "uuid": uuid, "vless_uri": uri})
            created += 1
        except Exception as e:
            db.rollback()
            results.append({"username": user_data.username, "error": str(e)})
    return {"created": created, "failed": len(payload.users) - created, "results": results}