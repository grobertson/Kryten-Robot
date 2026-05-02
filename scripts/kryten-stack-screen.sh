#!/usr/bin/env bash
set -euo pipefail

# Manage Kryten bot components in detached GNU screen sessions.
#
# Components:
#   robot      -> kryten-robot
#   userstats  -> kryten-userstats
#   moderator  -> kryten-moderator
#   economy    -> kryten-economy
#   llm        -> kryten-llm
#
# Usage:
#   ./kryten-stack-screen.sh start [all|component]
#   ./kryten-stack-screen.sh stop [all|component]
#   ./kryten-stack-screen.sh restart [all|component]
#   ./kryten-stack-screen.sh status
#   ./kryten-stack-screen.sh update [all|component]
#   ./kryten-stack-screen.sh logs <component> [lines]
#   ./kryten-stack-screen.sh attach <component>
#
# Optional environment variables:
#   STACK_PREFIX      Prefix for screen session names (default: kryten)
#   STACK_LOG_DIR     Directory for logs (default: ./logs)
#   STACK_CONFIG_FILE Config file path (default: ./kryten-stack.conf)
#   STACK_COMPONENTS  Space/comma-separated components for 'all'
#   ROBOT_ARGS        Extra args for kryten-robot
#   USERSTATS_ARGS    Extra args for kryten-userstats
#   MODERATOR_ARGS    Extra args for kryten-moderator
#   ECONOMY_ARGS      Extra args for kryten-economy
#   LLM_ARGS          Extra args for kryten-llm

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_PREFIX="${STACK_PREFIX:-kryten}"
STACK_LOG_DIR="${STACK_LOG_DIR:-$(pwd)/logs}"
STACK_CONFIG_FILE="${STACK_CONFIG_FILE:-$SCRIPT_DIR/kryten-stack.conf}"

ALL_COMPONENTS=(robot userstats moderator economy llm)
STACK_COMPONENTS="${STACK_COMPONENTS:-robot userstats moderator economy}"

if [[ -f "$STACK_CONFIG_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$STACK_CONFIG_FILE"
fi

parse_components() {
    local raw="$1"
    raw="${raw//,/ }"
    read -r -a ACTIVE_COMPONENTS <<< "$raw"
}

parse_components "$STACK_COMPONENTS"

if [[ "${#ACTIVE_COMPONENTS[@]}" -eq 0 ]]; then
    echo "Error: STACK_COMPONENTS resolved to an empty component list" >&2
    exit 1
fi

usage() {
    sed -n '1,50p' "$0"
}

require_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Error: required command not found: $cmd" >&2
        exit 1
    fi
}

session_name() {
    local component="$1"
    echo "${STACK_PREFIX}-${component}"
}

is_valid_component() {
    local component="$1"
    for c in "${ALL_COMPONENTS[@]}"; do
        if [[ "$c" == "$component" ]]; then
            return 0
        fi
    done
    return 1
}

resolve_targets() {
    local target="${1:-all}"

    if [[ "$target" == "all" ]]; then
        printf '%s\n' "${ACTIVE_COMPONENTS[@]}"
        return 0
    fi

    if is_valid_component "$target"; then
        echo "$target"
        return 0
    fi

    echo "Error: unknown target '$target'" >&2
    exit 1
}

package_for() {
    local component="$1"
    case "$component" in
        robot) echo "kryten-robot" ;;
        userstats) echo "kryten-userstats" ;;
        moderator) echo "kryten-moderator" ;;
        economy) echo "kryten-economy" ;;
        llm) echo "kryten-llm" ;;
        *)
            echo "Unknown component: $component" >&2
            exit 1
            ;;
    esac
}

args_for() {
    local component="$1"
    case "$component" in
        robot) echo "${ROBOT_ARGS:-}" ;;
        userstats) echo "${USERSTATS_ARGS:-}" ;;
        moderator) echo "${MODERATOR_ARGS:-}" ;;
        economy) echo "${ECONOMY_ARGS:-}" ;;
        llm) echo "${LLM_ARGS:-}" ;;
        *)
            echo "Unknown component: $component" >&2
            exit 1
            ;;
    esac
}

installed_bin_for() {
    local component="$1"
    local binary
    binary="$(package_for "$component")"

    if command -v "$binary" >/dev/null 2>&1; then
        command -v "$binary"
        return 0
    fi

    local default_bin_dir="${PIPX_BIN_DIR:-$HOME/.local/bin}"
    if [[ -x "$default_bin_dir/$binary" ]]; then
        echo "$default_bin_dir/$binary"
        return 0
    fi

    return 1
}

is_running() {
    local component="$1"
    local session
    session="$(session_name "$component")"
    screen -list | grep -q "[[:space:]]${session}[[:space:]]"
}

ensure_installed() {
    local component="$1"
    local package
    package="$(package_for "$component")"

    if installed_bin_for "$component" >/dev/null 2>&1; then
        return 0
    fi

    echo "Installing $package with pipx..."
    pipx install "$package"
}

update_component() {
    local component="$1"
    local package
    package="$(package_for "$component")"

    echo "Updating $package with pipx..."
    if ! pipx upgrade "$package"; then
        pipx install "$package"
    fi
}

start_component() {
    local component="$1"
    local session log_file bin extra_args cmd

    ensure_installed "$component"

    if is_running "$component"; then
        echo "$component already running in screen session $(session_name "$component")"
        return 0
    fi

    bin="$(installed_bin_for "$component")"
    extra_args="$(args_for "$component")"
    session="$(session_name "$component")"
    log_file="$STACK_LOG_DIR/${component}.log"

    mkdir -p "$STACK_LOG_DIR"

    cmd="$bin $extra_args"
    echo "Starting $component in screen session $session"
    screen -dmS "$session" bash -lc "exec $cmd >> '$log_file' 2>&1"
}

stop_component() {
    local component="$1"
    local session
    session="$(session_name "$component")"

    if is_running "$component"; then
        echo "Stopping $component ($session)"
        screen -S "$session" -X quit
    else
        echo "$component is not running"
    fi
}

status_all() {
    local component
    for component in "${ACTIVE_COMPONENTS[@]}"; do
        if is_running "$component"; then
            echo "$component: running ($(session_name "$component"))"
        else
            echo "$component: stopped"
        fi
    done
}

logs_component() {
    local component="$1"
    local lines="${2:-80}"
    local log_file="$STACK_LOG_DIR/${component}.log"

    if [[ ! -f "$log_file" ]]; then
        echo "No log file yet for $component: $log_file"
        return 1
    fi

    tail -n "$lines" "$log_file"
}

attach_component() {
    local component="$1"
    local session
    session="$(session_name "$component")"

    if ! is_running "$component"; then
        echo "$component is not running"
        exit 1
    fi

    echo "Attaching to $session (detach with Ctrl+a then d)"
    exec screen -r "$session"
}

main() {
    require_cmd screen
    require_cmd pipx

    local action="${1:-}"
    local target="${2:-all}"

    case "$action" in
        start)
            while read -r component; do
                start_component "$component"
            done < <(resolve_targets "$target")
            ;;
        stop)
            while read -r component; do
                stop_component "$component"
            done < <(resolve_targets "$target")
            ;;
        restart)
            while read -r component; do
                stop_component "$component"
            done < <(resolve_targets "$target")
            while read -r component; do
                start_component "$component"
            done < <(resolve_targets "$target")
            ;;
        update)
            while read -r component; do
                update_component "$component"
            done < <(resolve_targets "$target")
            ;;
        status)
            status_all
            ;;
        logs)
            if [[ -z "${2:-}" ]]; then
                echo "Usage: $0 logs <component> [lines]" >&2
                exit 1
            fi
            if ! is_valid_component "$2"; then
                echo "Unknown component: $2" >&2
                exit 1
            fi
            logs_component "$2" "${3:-80}"
            ;;
        attach)
            if [[ -z "${2:-}" ]]; then
                echo "Usage: $0 attach <component>" >&2
                exit 1
            fi
            if ! is_valid_component "$2"; then
                echo "Unknown component: $2" >&2
                exit 1
            fi
            attach_component "$2"
            ;;
        *)
            usage
            exit 1
            ;;
    esac
}

main "$@"
