#!/usr/bin/env python3
"""
Accumulates live totals into a cumulative usage table.
Safe to run every minute – never modifies manager's bytes_used.
"""
import sqlite3
import requests
import time
import os

DB_PATH = "/var/lib/xhttp-manager/db.sqlite"
API_BASE = "http://127.0.0.1:7171"
TOKEN_FILE = "/etc/xhttp-manager/admin.token"

def get_admin_token():
    with open(TOKEN_FILE, 'r') as f:
        return f.read().strip()

def get_active_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE status = 'active'")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def get_live_total(username, token):
    url = f"{API_BASE}/api/v1/stats/users?username={username}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("total", 0)
    except Exception:
        pass
    return 0

def ensure_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cumulative_usage (
            username TEXT PRIMARY KEY,
            total_cumulative INTEGER DEFAULT 0,
            last_live_total INTEGER DEFAULT 0,
            updated_at INTEGER DEFAULT (strftime('%s','now'))
        )
    """)
    conn.commit()
    conn.close()

def update_cumulative(username, live_total):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT last_live_total, total_cumulative FROM cumulative_usage WHERE username = ?",
        (username,)
    )
    row = cursor.fetchone()
    if row:
        last_live, cum = row
        if live_total >= last_live:
            diff = live_total - last_live
            new_cum = cum + diff
        else:
            # Xray restarted – add the new live_total as new usage
            new_cum = cum + live_total
        cursor.execute(
            "UPDATE cumulative_usage SET last_live_total = ?, total_cumulative = ?, updated_at = strftime('%s','now') WHERE username = ?",
            (live_total, new_cum, username)
        )
    else:
        # First time: set cumulative = live_total
        cursor.execute(
            "INSERT INTO cumulative_usage (username, last_live_total, total_cumulative) VALUES (?, ?, ?)",
            (username, live_total, live_total)
        )
    conn.commit()
    conn.close()

def main():
    ensure_table()
    token = get_admin_token()
    users = get_active_users()
    for username in users:
        live = get_live_total(username, token)
        if live is not None:
            update_cumulative(username, live)

if __name__ == "__main__":
    main()