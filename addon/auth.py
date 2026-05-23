from fastapi import Request, HTTPException, status
import os

TOKEN_FILE = "/etc/xhttp-manager/admin.token"

def get_token():
    with open(TOKEN_FILE, 'r') as f:
        return f.read().strip()

async def verify_admin(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token or token != get_token():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token", "message": "Authorization required"}
        )