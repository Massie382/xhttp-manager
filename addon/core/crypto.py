"""UUID and token generation utilities."""
import uuid
import secrets

def generate_uuid() -> str:
    """Generate a random UUID (version 4)."""
    return str(uuid.uuid4())

def generate_admin_token() -> str:
    """Generate a secure random admin token."""
    return "xmgr_" + secrets.token_hex(32)
