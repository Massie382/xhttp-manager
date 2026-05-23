"""
Limits enforcer script: checks expiry, data caps, device limits.
Runs as a oneshot systemd service triggered by timer.
Reads all configurable values from config.toml.
"""
import time, json, re, os, sys, toml
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import SessionLocal, init_db
from db.models import User, AuditLog
from core.stats_client import get_all_user_stats
from core.config_manager import remove_client, add_client

# ── Terminal colour helpers ──────────────────────────────────────────────
_RED    = "\033[0;31m"
_GREEN  = "\033[0;32m"
_YELLOW = "\033[1;33m"
_CYAN   = "\033[0;36m"
_NC     = "\033[0m"

def _colour(col: str, text: str) -> str:
    return f"{col}{text}{_NC}"

# ── Load settings from config.toml ───────────────────────────────────────
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
DEVICE_WINDOW_MINUTES = _cfg.get('enforcer', {}).get('device_window_minutes', 5)
THROTTLE_MINUTES      = _cfg.get('enforcer', {}).get('device_throttle_minutes', 5)
LOG_PATH              = _cfg.get('xray', {}).get('access_log', '/var/log/xray/access.log')

# ── Regex for parsing the Xray access log ────────────────────────────────
LOG_LINE_RE = re.compile(
    r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) '
    r'accepted tcp:(\d+\.\d+\.\d+\.\d+):\d+ '
    r'\[.*?\] email: (\S+)'
)

def _count_devices_per_email(window_start: datetime) -> dict:
    ip_sets = defaultdict(set)
    try:
        with open(LOG_PATH, 'r') as f:
            for line in f:
                m = LOG_LINE_RE.match(line)
                if not m:
                    continue
                ts_str = m.group(1)
                ip = m.group(2)
                email = m.group(3)
                try:
                    ts = datetime.strptime(ts_str, "%Y/%m/%d %H:%M:%S")
                except ValueError:
                    continue
                if ts < window_start:
                    continue
                ip_sets[email].add(ip)
    except FileNotFoundError:
        pass
    return ip_sets

def enforce():
    init_db()
    db = SessionLocal()
    changes = 0
    try:
        now = int(time.time())
        now_dt = datetime.now()
        window_start = now_dt - timedelta(minutes=DEVICE_WINDOW_MINUTES)
        device_counts = _count_devices_per_email(window_start)

        active_users = db.query(User).filter(User.status == 'active').all()
        emails = [u.email_tag for u in active_users]
        stats_list = get_all_user_stats(emails)
        stats_map = {s['email']: s for s in stats_list}

        for user in active_users:
            stats = stats_map.get(user.email_tag)
            if stats:
                total_new = stats['total']
                if total_new > user.bytes_used:
                    user.bytes_used = total_new
                    db.commit()

            if user.expiry_at is not None and user.expiry_at <= now:
                _revoke_user(db, user, "expired")
                print(f"  {_colour(_RED, 'REVOKED')} {user.username} – expired")
                changes += 1
                continue

            if user.data_cap_bytes is not None and user.bytes_used >= user.data_cap_bytes:
                _revoke_user(db, user, "expired_quota")
                print(f"  {_colour(_RED, 'REVOKED')} {user.username} – quota exceeded "
                      f"({user.bytes_used / 1024**2:.1f} MB / {user.data_cap_bytes / 1024**2:.1f} MB)")
                changes += 1
                continue

            if user.max_devices is not None:
                current_devices = len(device_counts.get(user.email_tag, set()))
                if current_devices > user.max_devices:
                    user.status = "suspended"
                    db.commit()
                    _log_action(db, user.username, "suspend",
                                {"reason": "device_limit", "devices": current_devices})
                    remove_client(user.uuid)
                    print(f"  {_colour(_YELLOW, 'SUSPEND')} {user.username} – "
                          f"device limit ({current_devices} > {user.max_devices})")
                    changes += 1

        # Auto-unsuspend users who have been suspended longer than THROTTLE_MINUTES
        suspended_users = db.query(User).filter(User.status == 'suspended').all()
        for user in suspended_users:
            last_suspend = db.query(AuditLog)\
                .filter(AuditLog.username == user.username, AuditLog.action == 'suspend')\
                .order_by(AuditLog.ts.desc()).first()
            if last_suspend:
                elapsed_minutes = (now - last_suspend.ts) / 60
                if elapsed_minutes >= THROTTLE_MINUTES:
                    current_devices = len(device_counts.get(user.email_tag, set()))
                    if current_devices <= (user.max_devices or 999):
                        user.status = "active"
                        db.commit()
                        _log_action(db, user.username, "unsuspend",
                                    {"reason": "auto_unsuspend_after_throttle"})
                        add_client(user.uuid, user.email_tag)
                        print(f"  {_colour(_GREEN, 'UNSUSPEND')} {user.username}")
                        changes += 1

        db.commit()
        if changes == 0:
            print(f"  {_colour(_GREEN, 'OK')} all users compliant")
    except Exception as e:
        db.rollback()
        print(f"  {_colour(_RED, 'ERROR')} {e}", file=sys.stderr)
        raise
    finally:
        db.close()

def _revoke_user(db, user, reason):
    user.status = reason
    db.commit()
    remove_client(user.uuid)
    _log_action(db, user.username, "revoke", {"reason": reason})

def _log_action(db, username, action, detail=None):
    log = AuditLog(
        ts=int(time.time()),
        action=action,
        username=username,
        actor="enforcer",
        detail=json.dumps(detail) if detail else None
    )
    db.add(log)
    db.commit()

if __name__ == "__main__":
    print(f"{_CYAN}Enforcer run at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{_NC}")
    enforce()
    print(f"{_CYAN}Done.{_NC}")
