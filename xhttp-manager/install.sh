#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}xhttp-manager installer${NC}"

if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    exit 1
fi

if ! grep -qi 'ubuntu' /etc/os-release; then
    echo -e "${RED}Error: This installer supports Ubuntu only${NC}"
    exit 1
fi

if ! systemctl is-active --quiet xray; then
    echo -e "${RED}Error: Xray service not running. Ensure XHTTP-Installer has been deployed.${NC}"
    exit 1
fi

if [[ ! -f /usr/local/etc/xray/config.json ]]; then
    echo -e "${RED}Error: Xray config not found at /usr/local/etc/xray/config.json${NC}"
    exit 1
fi

INSTALL_LOG="/tmp/xhttp-install.log"
RELAY_URL=""
RELAY_PATH=""
if [[ -f "$INSTALL_LOG" ]]; then
    RELAY_URL=$(grep -oP 'Relay URL:\s*\K.*' "$INSTALL_LOG" || true)
    RELAY_PATH=$(grep -oP 'Relay Path:\s*\K.*' "$INSTALL_LOG" || true)
fi

if [[ -z "$RELAY_URL" ]]; then
    echo -e "${RED}Error: Could not determine relay URL from install log.${NC}"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADDON_DST="/opt/xhttp-manager"

echo -e "${GREEN}Installing addon to $ADDON_DST${NC}"

apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip jq curl sqlite3 rsync

# Use rsync to copy files
rsync -a --delete "$SCRIPT_DIR/" "$ADDON_DST/" --exclude '.git' --exclude '__pycache__'

echo "Setting up Python virtual environment..."
python3 -m venv "$ADDON_DST/venv"
"$ADDON_DST/venv/bin/pip" install --upgrade pip -q
"$ADDON_DST/venv/bin/pip" install -r "$ADDON_DST/requirements.txt" -q

# Enable Xray stats
echo "Configuring Xray stats API..."
"$ADDON_DST/venv/bin/python" -c "from addon.core.config_manager import enable_stats; enable_stats()"

mkdir -p /var/lib/xhttp-manager
cat > /var/lib/xhttp-manager/deployment.json <<EOL
{
  "relay_url": "$RELAY_URL",
  "relay_path": "${RELAY_PATH:-/}",
  "server_domain": "$(hostname -f)",
  "xray_port": 443,
  "platform": "unknown",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOL

# Migrate existing default user
echo "Migrating default user..."
DEFAULT_UUID=$(jq -r '.inbounds[0].settings.clients[0].id' /usr/local/etc/xray/config.json 2>/dev/null || true)
if [[ -n "$DEFAULT_UUID" && "$DEFAULT_UUID" != "null" ]]; then
    "$ADDON_DST/venv/bin/python" -c "
from addon.db.database import init_db, SessionLocal
from addon.db.models import User
from addon.core.uri_builder import build_vless_uri
import time
init_db()
db = SessionLocal()
existing = db.query(User).filter(User.uuid == '$DEFAULT_UUID').first()
if not existing:
    uri = build_vless_uri('$DEFAULT_UUID', 'default')
    user = User(
        username='default',
        uuid='$DEFAULT_UUID',
        email_tag='default@xhttp',
        status='active',
        created_at=int(time.time()),
        vless_uri=uri
    )
    db.add(user)
    db.commit()
db.close()
"
fi

# Admin token
mkdir -p /etc/xhttp-manager
if [[ ! -f /etc/xhttp-manager/admin.token ]]; then
    TOKEN="xmgr_$(openssl rand -hex 32)"
    echo "$TOKEN" > /etc/xhttp-manager/admin.token
    chmod 600 /etc/xhttp-manager/admin.token
fi

# Systemd units
cp "$ADDON_DST/systemd/xhttp-manager.service" /etc/systemd/system/
cp "$ADDON_DST/systemd/xhttp-enforcer.service" /etc/systemd/system/
cp "$ADDON_DST/systemd/xhttp-enforcer.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now xhttp-manager.service
systemctl enable --now xhttp-enforcer.timer

# CLI
cp "$ADDON_DST/addon/cli/xhttp_mgr.sh" /usr/local/bin/xhttp-mgr
chmod +x /usr/local/bin/xhttp-mgr

sleep 2
if curl -sf http://127.0.0.1:7171/api/v1/health >/dev/null; then
    echo -e "${GREEN}✔ xhttp-manager API is running${NC}"
else
    echo -e "${RED}⚠ API health check failed, check journalctl -u xhttp-manager${NC}"
fi

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║         xhttp-manager INSTALLED SUCCESSFULLY  ✔     ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  API:       http://127.0.0.1:7171  (localhost only)"
echo "  CLI:       xhttp-mgr --help"
echo "  Data:      /var/lib/xhttp-manager/"
echo "  Logs:      journalctl -u xhttp-manager"
echo ""
echo "  Admin Token (save this — shown only once):"
cat /etc/xhttp-manager/admin.token
echo ""
echo "  Quick Start:"
echo "    xhttp-mgr create_user alice --expiry-days 30 --data-cap 100"
echo "    xhttp-mgr list_users"
echo "    xhttp-mgr stats"