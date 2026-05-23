import sys, io
sys.path.insert(0, '/opt/xhttp-manager/addon')
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse, Response
from sqlalchemy.orm import Session
from db.database import SessionLocal
from db.models import User
from api.auth import verify_admin
import qrcode

router = APIRouter(prefix="/api/v1", tags=["config"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/users/{username}/config", dependencies=[Depends(verify_admin)])
def user_config(username: str, format: str = Query("uri"), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, detail="User not found")
    if format == "uri":
        return PlainTextResponse(content=user.vless_uri)
    elif format == "json":
        return JSONResponse(content={"id": user.uuid, "email": user.email_tag, "level": 0})
    elif format == "qr":
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(user.vless_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return Response(content=buf.getvalue(), media_type="image/png")
    else:
        raise HTTPException(400, detail="Invalid format")
