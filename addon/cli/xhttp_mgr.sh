#!/usr/bin/env bash
# xhttp-mgr CLI - manages XHTTP users via REST API

# ── Color definitions ──────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

MGMT_URL="http://127.0.0.1:7171"
TOKEN_FILE="/etc/xhttp-manager/admin.token"

if [[ ! -f "$TOKEN_FILE" ]]; then
    echo -e "${RED}Error: Admin token not found at $TOKEN_FILE${NC}" >&2
    exit 1
fi

TOKEN=$(cat "$TOKEN_FILE")

_api() {
    local method="$1"
    local path="$2"
    shift 2
    curl -sf --max-time 10 -X "$method" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        "$MGMT_URL$path" "$@"
}

_usage() {
    echo -e "${BOLD}Usage:${NC} xhttp-mgr <command> [options]"
    echo ""
    echo -e "${BOLD}Commands:${NC}"
    echo -e "  ${GREEN}create_user${NC}    <username> [--expiry-days N] [--data-cap N] [--max-devices N] [--note TEXT] [--output uri|json|qr]"
    echo -e "  ${RED}revoke_user${NC}    <username> [--force]"
    echo -e "  ${YELLOW}suspend_user${NC}   <username>"
    echo -e "  ${GREEN}unsuspend_user${NC} <username>"
    echo -e "  ${CYAN}extend_user${NC}    <username> --days N"
    echo -e "  ${CYAN}set_limits${NC}     <username> [--expiry-days N] [--data-cap N] [--max-devices N] [--reset-usage]"
    echo -e "  ${BOLD}list_users${NC}     [--status STATUS] [--format table|json|csv]"
    echo -e "  ${BOLD}export_config${NC}  <username> [--format uri|json|qr]"
    echo -e "  ${BOLD}bulk_create${NC}    --file CSV_FILE"
    echo -e "  ${BOLD}bulk_create${NC}    --count N --prefix PREFIX [--expiry-days N] [--data-cap N] [--max-devices N]"
    echo -e "  ${BOLD}stats${NC}          [username]"
    echo -e "  ${BOLD}auth${NC}           show|rotate"
    echo -e "  ${BOLD}db${NC}             backup|restore FILE|vacuum"
    echo -e "  ${BOLD}system${NC}         status|reload|logs"
    echo ""
    echo -e "  ${BOLD}--help${NC}         Show this message"
}

_require_param() {
    if [[ -z "$1" ]]; then
        echo -e "${RED}Error: missing required parameter${NC}" >&2
        exit 1
    fi
}

_do_create_user() {
    local username="$1"
    shift
    _require_param "$username"
    local expiry_days="" data_cap="" max_devices="" note="" output="uri"
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --expiry-days) expiry_days="$2"; shift 2 ;;
            --data-cap) data_cap="$2"; shift 2 ;;
            --max-devices) max_devices="$2"; shift 2 ;;
            --note) note="$2"; shift 2 ;;
            --output) output="$2"; shift 2 ;;
            *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
        esac
    done
    local payload="{\"username\":\"$username\""
    [[ -n "$expiry_days" ]] && payload="$payload, \"expiry_days\":$expiry_days"
    [[ -n "$data_cap" ]] && payload="$payload, \"data_cap_gb\":$data_cap"
    [[ -n "$max_devices" ]] && payload="$payload, \"max_devices\":$max_devices"
    [[ -n "$note" ]] && payload="$payload, \"note\":\"$note\""
    payload="$payload}"
    local resp=$(_api POST "/api/v1/users" -d "$payload")
    if [[ "$output" == "uri" ]]; then
        echo -e "${GREEN}$(echo "$resp" | jq -r '.vless_uri')${NC}"
    else
        echo "$resp" | jq .
    fi
}

_do_revoke_user() {
    local username="$1"
    shift
    local force=false
    if [[ "$1" == "--force" ]]; then force=true; fi
    if ! $force; then
        read -p "$(echo -e ${YELLOW}"Revoke user '$username'? (y/N) "${NC})" confirm
        [[ "$confirm" != "y" ]] && exit 0
    fi
    echo -e "${RED}$(_api DELETE "/api/v1/users/$username" | jq -r '.message')${NC}"
}

_do_suspend_user() {
    echo -e "${YELLOW}$(_api POST "/api/v1/users/$1/suspend" | jq -r '.message')${NC}"
}

_do_unsuspend_user() {
    echo -e "${GREEN}$(_api POST "/api/v1/users/$1/unsuspend" | jq -r '.message')${NC}"
}

_do_extend_user() {
    local username="$1"
    shift
    local days=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --days) days="$2"; shift 2 ;;
            *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
        esac
    done
    [[ -z "$days" ]] && { echo -e "${RED}Error: --days required${NC}" >&2; exit 1; }
    _api POST "/api/v1/users/$username/extend" -d "{\"days\":$days}" | jq .
}

_do_set_limits() {
    local username="$1"
    shift
    local expiry_days="" data_cap="" max_devices="" reset_usage="false"
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --expiry-days) expiry_days="$2"; shift 2 ;;
            --data-cap) data_cap="$2"; shift 2 ;;
            --max-devices) max_devices="$2"; shift 2 ;;
            --reset-usage) reset_usage="true"; shift ;;
            *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
        esac
    done
    local payload="{"
    local first=true
    [[ -n "$expiry_days" ]] && { $first && first=false || payload="$payload, "; payload="$payload\"expiry_days\":$expiry_days"; }
    [[ -n "$data_cap" ]] && { $first && first=false || payload="$payload, "; payload="$payload\"data_cap_gb\":$data_cap"; }
    [[ -n "$max_devices" ]] && { $first && first=false || payload="$payload, "; payload="$payload\"max_devices\":$max_devices"; }
    $first || payload="$payload, "
    payload="$payload\"reset_usage\":$reset_usage}"
    _api PATCH "/api/v1/users/$username" -d "$payload" | jq .
}

_do_list_users() {
    local status="active" format="table"
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --status) status="$2"; shift 2 ;;
            --format) format="$2"; shift 2 ;;
            *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
        esac
    done
    local resp=$(_api GET "/api/v1/users?status=$status&limit=1000")
    if [[ "$format" == "json" ]]; then
        echo "$resp" | jq .
    elif [[ "$format" == "csv" ]]; then
        echo "$resp" | jq -r '.users[] | [.username,.status,.expiry_at,.bytes_used,.data_cap_bytes,.max_devices,.vless_uri] | @csv'
    else
        echo -e "${BOLD}USERNAME   STATUS    EXPIRY      USED     CAP     DEVS  NOTE${NC}"
        echo "$resp" | jq -r '.users[] | "\(.username) \(.status) \(.expiry_at // "none") \(.bytes_used) \(.data_cap_bytes // "none") \(.max_devices // "-") \(.note // "")"' | column -t
    fi
}

_do_export_config() {
    local username="$1"
    shift
    local format="uri"
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --format) format="$2"; shift 2 ;;
            *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
        esac
    done
    if [[ "$format" == "qr" ]]; then
        _api GET "/api/v1/users/$username/config?format=qr" --output "qr_${username}.png"
        echo -e "${GREEN}QR saved to qr_${username}.png${NC}"
    else
        _api GET "/api/v1/users/$username/config?format=$format"
    fi
}

_do_bulk_create() {
    local file="" count="" prefix="" expiry_days="" data_cap="" max_devices=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --file) file="$2"; shift 2 ;;
            --count) count="$2"; shift 2 ;;
            --prefix) prefix="$2"; shift 2 ;;
            --expiry-days) expiry_days="$2"; shift 2 ;;
            --data-cap) data_cap="$2"; shift 2 ;;
            --max-devices) max_devices="$2"; shift 2 ;;
            *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
        esac
    done
    if [[ -n "$file" ]]; then
        local users_json="["
        local first=true
        while IFS=',' read -r username edays dcap mdevs note; do
            $first && first=false || users_json="$users_json, "
            local obj="{\"username\":\"$username\""
            [[ -n "$edays" ]] && obj="$obj, \"expiry_days\":$edays"
            [[ -n "$dcap" ]] && obj="$obj, \"data_cap_gb\":$dcap"
            [[ -n "$mdevs" ]] && obj="$obj, \"max_devices\":$mdevs"
            [[ -n "$note" ]] && obj="$obj, \"note\":\"$note\""
            obj="$obj}"
            users_json="$users_json$obj"
        done < "$file"
        users_json="$users_json]"
        _api POST "/api/v1/users/bulk" -d "{\"users\":$users_json}" | jq .
    elif [[ -n "$count" && -n "$prefix" ]]; then
        local users_json="["
        for i in $(seq 1 "$count"); do
            local username="${prefix}$(printf '%03d' $i)"
            local obj="{\"username\":\"$username\""
            [[ -n "$expiry_days" ]] && obj="$obj, \"expiry_days\":$expiry_days"
            [[ -n "$data_cap" ]] && obj="$obj, \"data_cap_gb\":$data_cap"
            [[ -n "$max_devices" ]] && obj="$obj, \"max_devices\":$max_devices"
            obj="$obj}"
            [[ $i -gt 1 ]] && users_json="$users_json, "
            users_json="$users_json$obj"
        done
        users_json="$users_json]"
        _api POST "/api/v1/users/bulk" -d "{\"users\":$users_json}" | jq .
    else
        echo -e "${RED}Error: specify --file or --count with --prefix${NC}" >&2
        exit 1
    fi
}

_do_stats() {
    if [[ -n "$1" ]]; then
        _api GET "/api/v1/stats/users" | jq --arg u "$1" '.[] | select(.username == $u)'
    else
        _api GET "/api/v1/stats" | jq .
    fi
}

_do_auth() {
    case "$1" in
        show)
            echo -e "${YELLOW}${BOLD}Current token:${NC} ${YELLOW}$TOKEN${NC}"
            ;;
        rotate)
            new_token=$(openssl rand -hex 32)
            echo "xmgr_$new_token" > "$TOKEN_FILE"
            echo -e "${YELLOW}${BOLD}Token rotated. Restart API service to apply.${NC}"
            systemctl restart xhttp-manager
            ;;
        *)
            echo -e "${RED}Unknown auth command: $1${NC}"; exit 1 ;;
    esac
}

_do_db() {
    case "$1" in
        backup) sqlite3 /var/lib/xhttp-manager/db.sqlite .dump ;;
        restore) sqlite3 /var/lib/xhttp-manager/db.sqlite < "$2" ;;
        vacuum) sqlite3 /var/lib/xhttp-manager/db.sqlite "VACUUM;"; echo -e "${GREEN}Database vacuumed${NC}" ;;
        *) echo -e "${RED}Unknown db command: $1${NC}"; exit 1 ;;
    esac
}

_do_system() {
    case "$1" in
        status)
            _api GET "/api/v1/health" | jq .
            echo ""
            echo -e "${BOLD}Enforcer timer:${NC}"
            systemctl is-active xhttp-enforcer.timer
            ;;
        reload) _api POST "/api/v1/system/reload" | jq . ;;
        logs) journalctl -u xray --no-pager -n 50 -f ;;
        *) echo -e "${RED}Unknown system command: $1${NC}"; exit 1 ;;
    esac
}

# Main dispatcher
COMMAND="$1"
case "$COMMAND" in
    create_user) shift; _do_create_user "$@" ;;
    revoke_user) shift; _do_revoke_user "$@" ;;
    suspend_user) shift; _do_suspend_user "$@" ;;
    unsuspend_user) shift; _do_unsuspend_user "$@" ;;
    extend_user) shift; _do_extend_user "$@" ;;
    set_limits) shift; _do_set_limits "$@" ;;
    list_users) shift; _do_list_users "$@" ;;
    export_config) shift; _do_export_config "$@" ;;
    bulk_create) shift; _do_bulk_create "$@" ;;
    stats) shift; _do_stats "$@" ;;
    auth) shift; _do_auth "$@" ;;
    db) shift; _do_db "$@" ;;
    system) shift; _do_system "$@" ;;
    --help|help) _usage ;;
    *)
        echo -e "${RED}Unknown command: $COMMAND${NC}" >&2
        _usage
        exit 1
        ;;
esac
