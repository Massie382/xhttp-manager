#!/usr/bin/env bash
set -euo pipefail

# ── Color definitions ──────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Configuration
ADDON_SRC="/opt/xhttp-manager"
DATA_DIR="/var/lib/xhttp-manager"
CONFIG_DIR="/etc/xhttp-manager"
CLI_BIN="/usr/local/bin/xhttp-mgr"
XRAY_CONFIG="/usr/local/etc/xray/config.json"
SYSTEMD_UNITS=(
    "/etc/systemd/system/xhttp-manager.service"
    "/etc/systemd/system/xhttp-enforcer.service"
    "/etc/systemd/system/xhttp-enforcer.timer"
)

PURGE=false
REMOVE_USER_DATA=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --purge) PURGE=true; shift ;;
        --remove-user-data) REMOVE_USER_DATA=true; shift ;;
        *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
    esac
done

echo -e "${CYAN}${BOLD}xhttp-manager uninstaller${NC}"
echo ""

if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}Error: must run as root${NC}"
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo -e "${RED}Error: python3 required to restore Xray config${NC}"
    exit 1
fi

# Stop and disable services
echo -e "${CYAN}Stopping services...${NC}"
if systemctl is-active --quiet xhttp-manager.service; then
    systemctl stop xhttp-manager.service
    echo -e "  ${GREEN}OK${NC} xhttp-manager stopped"
fi
if systemctl is-active --quiet xhttp-enforcer.timer; then
    systemctl stop xhttp-enforcer.timer
    echo -e "  ${GREEN}OK${NC} enforcer timer stopped"
fi
if systemctl is-enabled --quiet xhttp-manager.service 2>/dev/null; then
    systemctl disable xhttp-manager.service
fi
if systemctl is-enabled --quiet xhttp-enforcer.timer 2>/dev/null; then
    systemctl disable xhttp-enforcer.timer
fi

# Restore Xray config
if [[ -f "$XRAY_CONFIG" ]]; then
    echo -e "${CYAN}Restoring Xray config...${NC}"
    BACKUP="${XRAY_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$XRAY_CONFIG" "$BACKUP"
    echo -e "  ${GREEN}OK${NC} Backup: $BACKUP"
    python3 <<'PYEOF'
import json, sys
try:
    with open('/usr/local/etc/xray/config.json', 'r') as f:
        cfg = json.load(f)
    cfg.pop('stats', None)
    cfg.pop('api', None)
    cfg.pop('policy', None)
    if 'inbounds' in cfg:
        cfg['inbounds'] = [i for i in cfg['inbounds'] if i.get('tag') != 'api']
    with open('/usr/local/etc/xray/config.json', 'w') as f:
        json.dump(cfg, f, indent=2)
    print("  \033[0;32mOK\033[0m Config cleaned")
except Exception as e:
    print(f"  \033[0;31mFAIL\033[0m Error: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
    if systemctl restart xray 2>/dev/null; then
        echo -e "  ${GREEN}OK${NC} Xray restarted with restored config"
    else
        echo -e "  ${YELLOW}WARN${NC} Xray restart failed (start manually: systemctl start xray)"
    fi
fi

# Remove unit files
echo -e "${CYAN}Removing systemd units...${NC}"
for unit in "${SYSTEMD_UNITS[@]}"; do
    if [[ -f "$unit" ]]; then
        rm -f "$unit"
        echo -e "  ${GREEN}OK${NC} removed $unit"
    fi
done
systemctl daemon-reload

# Remove addon files
echo -e "${CYAN}Removing addon files...${NC}"
rm -f "$CLI_BIN"
echo -e "  ${GREEN}OK${NC} removed $CLI_BIN"
rm -rf "$ADDON_SRC"
echo -e "  ${GREEN}OK${NC} removed $ADDON_SRC"
rm -rf "$CONFIG_DIR"
echo -e "  ${GREEN}OK${NC} removed $CONFIG_DIR"

# Data directory
if [[ "$REMOVE_USER_DATA" == "true" ]] || [[ "$PURGE" == "true" ]]; then
    rm -rf "$DATA_DIR"
    echo -e "${GREEN}OK${NC} User data removed"
else
    if [[ -d "$DATA_DIR" ]]; then
        echo -e "${YELLOW}User data preserved at $DATA_DIR${NC}"
        echo -e "  ${YELLOW}Use --remove-user-data to delete${NC}"
    fi
fi

echo ""
echo -e "${GREEN}${BOLD}Uninstall complete.${NC}"
