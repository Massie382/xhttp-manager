import sys, subprocess, json
sys.path.insert(0, '/opt/xhttp-manager/addon')
from typing import Dict, List

def _run_statsquery(pattern: str = "") -> Dict[str, int]:
    cmd = ["/usr/local/bin/xray", "api", "statsquery", "-server", "127.0.0.1:10085", "-pattern", pattern]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=True)
        data = json.loads(proc.stdout)
        stats = {}
        for item in data.get("stat", []):
            stats[item["name"]] = int(item.get("value", 0))
        return stats
    except:
        return {}

def get_user_stats(email: str) -> Dict[str, int]:
    stats = _run_statsquery(f"user>>>{email}>>>traffic>>>")
    return {
        "uplink": stats.get(f"user>>>{email}>>>traffic>>>uplink", 0),
        "downlink": stats.get(f"user>>>{email}>>>traffic>>>downlink", 0),
        "total": stats.get(f"user>>>{email}>>>traffic>>>uplink", 0) + stats.get(f"user>>>{email}>>>traffic>>>downlink", 0)
    }

def get_all_user_stats(emails: List[str]) -> List[Dict]:
    if not emails:
        return []
    all_stats = _run_statsquery("user>>>")
    results = []
    for email in emails:
        up = all_stats.get(f"user>>>{email}>>>traffic>>>uplink", 0)
        down = all_stats.get(f"user>>>{email}>>>traffic>>>downlink", 0)
        results.append({"email": email, "uplink": up, "downlink": down, "total": up + down})
    return results
