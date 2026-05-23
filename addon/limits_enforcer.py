"""
Limits enforcer script: checks expiry, data caps, device limits.
Runs as a oneshot systemd service triggered by timer.
"""
import time, json, re, os, sys
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.database import SessionLocal, init_db
from db.models import User, AuditLog
from core.stats_client import get_all_user_stats
from core.config_manager import remove_client, add_client

LOG_PATH = "/var/log/xray/access.log"
DEVICE_WINDOW_MINUTES = 5
THROTTLE_MINUTES = 5

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
                continue

            if user.data_cap_bytes is not None and user.bytes_used >= user.data_cap_bytes:
                _revoke_user(db, user, "expired_quota")
                continue

            if user.max_devices is not None:
                current_devices = len(device_counts.get(user.email_tag, set()))
                if current_devices > user.max_devices:
                    user.status = "suspended"
                    db.commit()
                    _log_action(db, user.username, "suspend",
                                {"reason": "device_limit", "devices": current_devices})
                    remove_client(user.uuid)

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

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Enforcer error: {e}", file=sys.stderr)
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
    enforce()
