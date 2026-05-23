"""Build vless:// URI for a user."""
import json
from typing import Any, Dict

def load_deployment() -> Dict[str, Any]:
    try:
        with open("/var/lib/xhttp-manager/deployment.json", "r") as f:
            content = f.read()
            # Strip any non-printable characters that might corrupt JSON
            import re
            content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', content)
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # Return a safe fallback so the API doesn't crash
        return {
            "relay_url": "",
            "relay_path": "/",
            "server_domain": "unknown",
            "xray_port": 443,
            "platform": "unknown",
            "installed_at": ""
        }

def build_vless_uri(uuid: str, username: str) -> str:
    dep = load_deployment()
    relay_url = dep.get("relay_url", "")
    if not relay_url:
        # Fallback: try to construct from server_domain
        relay_url = f"https://{dep.get('server_domain', 'localhost')}"
    relay_host = relay_url.replace("https://", "").replace("http://", "").rstrip("/")
    relay_path = dep.get("relay_path", "/")
    return (
        f"vless://{uuid}@{relay_host}:443"
        f"?type=xhttp&security=tls&sni={relay_host}"
        f"&path={relay_path}#{username}"
    )
