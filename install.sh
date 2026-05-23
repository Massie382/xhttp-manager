#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------------------------
# Robust way to find the install directory, even if the script is piped from curl
# ------------------------------------------------------------------------------
if [[ -z "${BASH_SOURCE[0]:-}" || ! -f "${BASH_SOURCE[0]}" ]]; then
    # We are being piped (curl | bash). Clone the repo and re-execute.
    REPO_URL="https://github.com/Massie382/xhttp-manager.git"
    TMPDIR=$(mktemp -d /tmp/xhttp-manager.XXXXXX)
    git clone --depth 1 "$REPO_URL" "$TMPDIR"
    cd "$TMPDIR"
    exec bash install.sh   # re-run the real file
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADDON_DST="/opt/xhttp-manager"

# ── Color definitions ──────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}${BOLD}  xhttp-manager installer${NC}"
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    exit 1
fi

if ! grep -qi 'ubuntu' /etc/os-release; then
    echo -e "${RED}Error: This installer supports Ubuntu only${NC}"
    exit 1
fi

echo -e "${CYAN}[1/6] Checking base system...${NC}"
if ! systemctl is-active --quiet xray; then
    echo -e "${RED}Error: Xray service not running. Ensure XHTTP-Installer has been deployed.${NC}"
    exit 1
fi
echo -e "      ${GREEN}✔ Xray is running${NC}"

if [[ ! -f /usr/local/etc/xray/config.json ]]; then
    echo -e "${RED}Error: Xray config not found at /usr/local/etc/xray/config.json${NC}"
    exit 1
fi
echo -e "      ${GREEN}✔ Xray config found${NC}"

INSTALL_LOG="/tmp/xhttp-install.log"
RELAY_URL=""
RELAY_PATH=""
if [[ -f "$INSTALL_LOG" ]]; then
    RELAY_URL=$(grep -oP 'Relay\s*URL\s*:\s*\K\S+' "$INSTALL_LOG" || true)
    RELAY_PATH=$(grep -oP 'Relay\s*Path\s*:\s*\K\S+' "$INSTALL_LOG" || true)
fi

if [[ -z "$RELAY_URL" ]]; then
    echo -e "${RED}Error: Could not determine relay URL from install log.${NC}"
    exit 1
fi
echo -e "      ${GREEN}✔ Relay URL detected: ${RELAY_URL}${NC}"

echo ""
echo -e "${CYAN}[2/6] Installing system packages...${NC}"
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip jq curl sqlite3 rsync
echo -e "      ${GREEN}✔ Dependencies installed${NC}"

echo -e "${CYAN}[3/6] Copying addon files to ${ADDON_DST}...${NC}"
rsync -a --delete "$SCRIPT_DIR/" "$ADDON_DST/" --exclude '.git' --exclude '__pycache__'
echo -e "      ${GREEN}✔ Files copied${NC}"

echo -e "${CYAN}[4/6] Setting up Python virtual environment...${NC}"
python3 -m venv "$ADDON_DST/venv"
"$ADDON_DST/venv/bin/pip" install --upgrade pip -q
"$ADDON_DST/venv/bin/pip" install -r "$ADDON_DST/requirements.txt" -q
echo -e "      ${GREEN}✔ Python environment ready${NC}"

echo -e "${CYAN}[5/6] Configuring Xray stats API...${NC}"
"$ADDON_DST/venv/bin/python" -c "from addon.core.config_manager import enable_stats; enable_stats()"
echo -e "      ${GREEN}✔ Xray stats API enabled${NC}"

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

echo -e "${CYAN}[6/6] Migrating default user...${NC}"
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
    echo -e "      ${GREEN}✔ Default user migrated${NC}"
else
    echo -e "      ${YELLOW}⚠ No existing user to migrate${NC}"
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
echo ""
if curl -sf http://127.0.0.1:7171/api/v1/health >/dev/null; then
    echo -e "${GREEN}${BOLD}✔ xhttp-manager API is running${NC}"
else
    echo -e "${RED}${BOLD}⚠ API health check failed, check: journalctl -u xhttp-manager${NC}"
fi

echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║     xhttp-manager INSTALLED SUCCESSFULLY  ✔             ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}API:${NC}       http://127.0.0.1:7171  (localhost only)"
echo -e "  ${BOLD}CLI:${NC}       xhttp-mgr --help"
echo -e "  ${BOLD}Data:${NC}      /var/lib/xhttp-manager/"
echo -e "  ${BOLD}Logs:${NC}      journalctl -u xhttp-manager"
echo ""
echo -e "  ${YELLOW}${BOLD}Admin Token (save this — shown only once):${NC}"
echo -e "  ${YELLOW}$(cat /etc/xhttp-manager/admin.token)${NC}"
echo ""
echo -e "  ${BOLD}Quick Start:${NC}"
echo -e "    ${GREEN}xhttp-mgr create_user alice --expiry-days 30 --data-cap 100${NC}"
echo -e "    xhttp-mgr list_users"
echo -e "    xhttp-mgr stats"
