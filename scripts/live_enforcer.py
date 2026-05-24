#!/usr/bin/env python3
"""
Lightweight enforcer that uses live API data to revoke users who exceed their cap.
Does not modify bytes_used; works independently.
"""
import sqlite3
import requests
import time

DB_PATH = "/var/lib/xhttp-manager/db.sqlite"
API_BASE = "http://127.0.0.1:7171"
TOKEN_FILE = "/etc/xhttp-manager/admin.token"

def get_admin_token():
    with open(TOKEN_FILE, 'r') as f:
        return f.read().strip()

def get_active_users_with_cap():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT username, data_cap_bytes FROM users WHERE status = 'active' AND data_cap_bytes IS NOT NULL")
    users = cursor.fetchall()
    conn.close()
    return users

def revoke_user(username):
    headers = {"Authorization": f"Bearer {get_admin_token()}"}
    url = f"{API_BASE}/api/v1/users/{username}"
    resp = requests.delete(url, headers=headers)
    return resp.status_code == 200

def get_live_total(username):
    url = f"{API_BASE}/api/v1/stats/users?username={username}"
    headers = {"Authorization": f"Bearer {get_admin_token()}"}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("total", 0)
    except Exception:
        pass
    return 0

def main():
    users = get_active_users_with_cap()
    for username, cap_bytes in users:
        live_total = get_live_total(username)
        if live_total >= cap_bytes:
            print(f"Revoking {username}: {live_total} >= {cap_bytes}")
            if revoke_user(username):
                print(f"✅ Revoked {username}")
            else:
                print(f"❌ Failed to revoke {username}")

if __name__ == "__main__":
    main()