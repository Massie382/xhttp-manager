"""Build vless:// URI for a user."""
import json
from typing import Any, Dict

def load_deployment() -> Dict[str, Any]:
    with open("/var/lib/xhttp-manager/deployment.json", "r") as f:
        return json.load(f)

def build_vless_uri(uuid: str, username: str) -> str:
    dep = load_deployment()
    relay_url = dep["relay_url"]
    relay_host = relay_url.replace("https://", "").replace("http://", "").rstrip("/")
    relay_path = dep.get("relay_path", "/")
    return (
        f"vless://{uuid}@{relay_host}:443"
        f"?type=xhttp&security=tls&sni={relay_host}"
        f"&path={relay_path}#{username}"
    )