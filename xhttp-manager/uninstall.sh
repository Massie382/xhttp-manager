#!/usr/bin/env bash
set -euo pipefail

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
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ $EUID -ne 0 ]]; then
    echo "Error: must run as root"
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "Error: python3 required to restore Xray config"
    exit 1
fi

# Stop and disable services
echo "→ Stopping services..."
if systemctl is-active --quiet xhttp-manager.service; then
    systemctl stop xhttp-manager.service
    echo "  ✔ xhttp-manager stopped"
fi
if systemctl is-active --quiet xhttp-enforcer.timer; then
    systemctl stop xhttp-enforcer.timer
    echo "  ✔ enforcer timer stopped"
fi
if systemctl is-enabled --quiet xhttp-manager.service 2>/dev/null; then
    systemctl disable xhttp-manager.service
fi
if systemctl is-enabled --quiet xhttp-enforcer.timer 2>/dev/null; then
    systemctl disable xhttp-enforcer.timer
fi

# Restore Xray config
if [[ -f "$XRAY_CONFIG" ]]; then
    echo "→ Restoring Xray config..."
    BACKUP="${XRAY_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$XRAY_CONFIG" "$BACKUP"
    echo "  ✔ Backup: $BACKUP"
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
    print("  ✔ Config cleaned")
except Exception as e:
    print(f"  ✘ Error: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
    systemctl restart xray 2>/dev/null || echo "  ⚠ Xray restart failed (if not running, start manually)"
fi

# Remove unit files
echo "→ Removing systemd units..."
for unit in "${SYSTEMD_UNITS[@]}"; do
    if [[ -f "$unit" ]]; then rm -f "$unit"; echo "  ✔ removed $unit"; fi
done
systemctl daemon-reload

# Remove addon files
echo "→ Removing addon files..."
rm -f "$CLI_BIN"
rm -rf "$ADDON_SRC"
rm -rf "$CONFIG_DIR"

# Data directory
if [[ "$REMOVE_USER_DATA" == "true" ]] || [[ "$PURGE" == "true" ]]; then
    rm -rf "$DATA_DIR"
    echo "✔ User data removed"
else
    if [[ -d "$DATA_DIR" ]]; then
        echo "→ User data preserved at $DATA_DIR (use --remove-user-data to delete)"
    fi
fi

echo "✓ Uninstall complete."