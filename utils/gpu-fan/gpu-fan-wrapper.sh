#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Watchdog wrapper for gpu-fan-control PID controller
# This is the parent process — it ensures fans are always safe.

set -euo pipefail

CONTROLLER="/usr/local/bin/gpu-fan-control.sh"
HEARTBEAT="/tmp/gpu-fan-heartbeat"
HEARTBEAT_TIMEOUT=30
CHECK_INTERVAL=5
LOG_TAG="gpu-fan-watchdog"
CONTROLLER_PID=""

log() {
    logger -t "$LOG_TAG" "$1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >&2
}

set_fans_max() {
    ipmitool raw 0x30 0x30 0x01 0x00 2>/dev/null || true
    local hex
    hex=$(printf '0x%02x' 100)
    ipmitool raw 0x30 0x30 0x02 0xff "$hex" 2>/dev/null || true
    log "SAFETY: Fans set to 100%"
}

set_fans_auto() {
    ipmitool raw 0x30 0x30 0x01 0x01 2>/dev/null || true
    log "Fans restored to AUTOMATIC mode"
}

kill_controller() {
    if [ -n "$CONTROLLER_PID" ] && kill -0 "$CONTROLLER_PID" 2>/dev/null; then
        kill "$CONTROLLER_PID" 2>/dev/null
        wait "$CONTROLLER_PID" 2>/dev/null || true
        log "Killed controller PID $CONTROLLER_PID"
    fi
    CONTROLLER_PID=""
}

start_controller() {
    kill_controller
    rm -f "$HEARTBEAT"
    bash "$CONTROLLER" &
    CONTROLLER_PID=$!
    log "Started controller PID $CONTROLLER_PID"
}

is_heartbeat_stale() {
    if [ ! -f "$HEARTBEAT" ]; then
        return 0
    fi
    local last_beat now age
    last_beat=$(cat "$HEARTBEAT" 2>/dev/null) || return 0
    now=$(date +%s)
    age=$(( now - last_beat ))
    [ "$age" -gt "$HEARTBEAT_TIMEOUT" ]
}

cleanup() {
    log "Shutting down — restoring automatic fan control"
    kill_controller
    set_fans_auto
    rm -f "$HEARTBEAT"
    exit 0
}

trap cleanup SIGTERM SIGINT SIGHUP

# --- Main ---
log "Starting watchdog wrapper"

# SAFETY FIRST: set fans to max before anything else
set_fans_max

# Start PID controller
start_controller

# Watchdog loop
while true; do
    sleep "$CHECK_INTERVAL"

    # Check if controller is alive
    if [ -n "$CONTROLLER_PID" ] && ! kill -0 "$CONTROLLER_PID" 2>/dev/null; then
        log "WARNING: Controller died — restarting"
        set_fans_max
        start_controller
        continue
    fi

    # Check heartbeat staleness
    if is_heartbeat_stale; then
        log "WARNING: Controller heartbeat stale — killing and restarting"
        set_fans_max
        kill_controller
        start_controller
        continue
    fi
done
