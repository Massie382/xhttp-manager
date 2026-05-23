"""Manage Xray configuration file. All paths and limits are read from config.toml."""
import json, os, shutil, subprocess, toml
from pathlib import Path
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Load settings from config.toml
# ---------------------------------------------------------------------------
def _load_config():
    config_paths = [
        os.environ.get('XHTTP_MANAGER_CONFIG', ''),
        '/etc/xhttp-manager/config.toml',
        os.path.join(os.path.dirname(__file__), '..', 'config.toml'),
    ]
    for cp in config_paths:
        try:
            if cp and os.path.exists(cp):
                return toml.load(cp)
        except Exception:
            pass
    return {}

_cfg = _load_config()
CONFIG_PATH = Path(_cfg.get('xray', {}).get('config_path', '/usr/local/etc/xray/config.json'))
BACKUP_DIR  = Path(_cfg.get('storage', {}).get('backup_dir', '/var/lib/xhttp-manager/backups'))
MAX_BACKUPS = _cfg.get('storage', {}).get('max_backups', 20)
RELOAD_CMD  = _cfg.get('xray', {}).get('reload_cmd', 'systemctl restart xray').split()

# ---------------------------------------------------------------------------
def _backup_config():
    import time
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    shutil.copy2(CONFIG_PATH, BACKUP_DIR / f"config.{timestamp}.json")
    backups = sorted(BACKUP_DIR.glob("config.*.json"))
    while len(backups) > MAX_BACKUPS:
        backups.pop(0).unlink()

def read_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def write_config(config: Dict[str, Any], reload: bool = True):
    _backup_config()
    tmp_path = CONFIG_PATH.with_suffix('.tmp')
    with open(tmp_path, 'w') as f:
        json.dump(config, f, indent=2)
    tmp_path.rename(CONFIG_PATH)
    if reload:
        subprocess.run(RELOAD_CMD, check=True)

def add_client(uuid: str, email: str):
    config = read_config()
    inbound = config["inbounds"][0]
    clients = inbound.setdefault("settings", {}).setdefault("clients", [])
    if not any(c["id"] == uuid for c in clients):
        clients.append({"id": uuid, "email": email, "level": 0})
        inbound["settings"]["decryption"] = "none"
        write_config(config)

def remove_client(uuid: str):
    config = read_config()
    inbound = config["inbounds"][0]
    clients = inbound["settings"]["clients"]
    inbound["settings"]["clients"] = [c for c in clients if c["id"] != uuid]
    write_config(config)

def get_clients() -> List[Dict[str, Any]]:
    config = read_config()
    return config["inbounds"][0]["settings"]["clients"]

def enable_stats():
    """Inject stats, api, and policy blocks; use built-in API listener."""
    config = read_config()
    if "stats" not in config:
        config["stats"] = {}
    if "api" not in config:
        config["api"] = {
            "tag": "api",
            "services": ["StatsService"]
        }
    config["api"]["listen"] = "127.0.0.1:10085"
    if "policy" not in config:
        config["policy"] = {
            "levels": {
                "0": {
                    "statsUserUplink": True,
                    "statsUserDownlink": True
                }
            },
            "system": {
                "statsInboundDownlink": True,
                "statsInboundUplink": True
            }
        }
    # Remove any previous dokodemo-door inbound tagged 'api'
    config["inbounds"] = [i for i in config.get("inbounds", []) if i.get("tag") != "api"]
    write_config(config)
