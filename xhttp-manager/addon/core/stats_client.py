"""Query Xray stats via CLI tool."""
import json
import subprocess
from typing import Dict, List

def _run_statsquery(pattern: str = "") -> Dict[str, int]:
    cmd = [
        "/usr/local/bin/xray", "api", "statsquery",
        "--server=127.0.0.1:10085",
        "-pattern", pattern
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    stats = {}
    for item in data.get("stat", []):
        name = item["name"]
        value = int(item.get("value", 0))
        stats[name] = value
    return stats

def get_user_stats(email: str) -> Dict[str, int]:
    pattern = f"user>>>{email}>>>traffic>>>"
    raw = _run_statsquery(pattern)
    uplink = raw.get(f"user>>>{email}>>>traffic>>>uplink", 0)
    downlink = raw.get(f"user>>>{email}>>>traffic>>>downlink", 0)
    return {"uplink": uplink, "downlink": downlink, "total": uplink + downlink}

def get_all_user_stats(emails: List[str]) -> List[Dict[str, any]]:
    if not emails:
        return []
    pattern = "user>>>"
    raw = _run_statsquery(pattern)
    results = []
    for email in emails:
        uplink = raw.get(f"user>>>{email}>>>traffic>>>uplink", 0)
        downlink = raw.get(f"user>>>{email}>>>traffic>>>downlink", 0)
        results.append({
            "email": email,
            "uplink": uplink,
            "downlink": downlink,
            "total": uplink + downlink
        })
    return results