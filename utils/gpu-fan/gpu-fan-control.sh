#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# PID controller for GPU fan control on Dell PowerEdge with passively cooled GPU (Tesla P4)
# This script is the child process — monitored by gpu-fan-wrapper.sh
#
# NOTE: Dell PowerEdge manual IPMI fan control caps at ~6,500 RPM.
# BMC auto mode can reach 16,000+ RPM but is slower to respond.
# This PID runs in manual mode for direct control.

set -euo pipefail

# --- PID Parameters ---
SETPOINT=67
KP="8.0"
KI="0.5"
KD="2.0"
MIN_FAN=30
MAX_FAN=100
INTERVAL=10

# --- State ---
integral="0"
prev_error=""
current_fan=$MAX_FAN
HEARTBEAT="/tmp/gpu-fan-heartbeat"
LOG_TAG="gpu-fan-control"

log() {
    logger -t "$LOG_TAG" "$1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >&2
}

clamp() {
    local val=$1
    local lo=$2
    local hi=$3
    if   (( $(echo "$val < $lo" | bc -l) )); then echo "$lo"
    elif (( $(echo "$val > $hi" | bc -l) )); then echo "$hi"
    else echo "$val"
    fi
}

to_int() {
    printf '%.0f' "$1" | tr -d '-'
}

set_fan_mode_manual() {
    ipmitool raw 0x30 0x30 0x01 0x00 2>/dev/null || true
}

set_fan_mode_auto() {
    ipmitool raw 0x30 0x30 0x01 0x01 2>/dev/null || true
}

set_fan_speed() {
    local pct
    pct=$(to_int "$1")
    if [ "$pct" -gt 100 ]; then pct=100; fi
    if [ "$pct" -lt "$MIN_FAN" ]; then pct=$MIN_FAN; fi
    local hex
    hex=$(printf '0x%02x' "$pct")
    if ! ipmitool raw 0x30 0x30 0x02 0xff "$hex" 2>/dev/null; then
        log "ERROR: ipmitool failed — cannot set fan speed"
        exit 1
    fi
    current_fan=$pct
}

get_gpu_temp() {
    local temp
    temp=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | tr -d '[:space:]')
    if [ -z "$temp" ] || ! [[ "$temp" =~ ^[0-9]+$ ]]; then
        return 1
    fi
    echo "$temp"
}

pid_step() {
    local temp=$1
    local dt=$INTERVAL

    # error: positive when too hot
    local error
    error=$(echo "$temp - $SETPOINT" | bc -l)

    # Proportional
    local p_term
    p_term=$(echo "$KP * $error" | bc -l)

    # Integral with anti-windup
    local new_integral
    new_integral=$(echo "$integral + $error * $dt" | bc -l)
    local max_integral
    max_integral=$(echo "scale=4; ($MAX_FAN - $MIN_FAN) / $KI / $dt * 0.5" | bc -l)
    local neg_max_integral
    neg_max_integral=$(echo "0 - $max_integral" | bc -l)
    integral=$(clamp "$new_integral" "$neg_max_integral" "$max_integral")

    local i_term
    i_term=$(echo "$KI * $integral" | bc -l)

    # Derivative
    local d_term="0"
    if [ -n "$prev_error" ]; then
        local raw_d
        raw_d=$(echo "($error - $prev_error) / $dt" | bc -l)
        d_term=$(echo "$KD * $raw_d" | bc -l)
    fi

    prev_error="$error"

    # PID output
    local output
    output=$(echo "$p_term + $i_term + $d_term" | bc -l)
    output=$(clamp "$output" "$MIN_FAN" "$MAX_FAN")

    # HARD CEILING: never let GPU exceed 80°C
    if [ "$temp" -ge 80 ]; then
        output=100
        log "CRITICAL: temp>=80°C — overriding to 100%"
    fi

    local output_int
    output_int=$(to_int "$output")

    # Only issue IPMI command if speed changed
    if [ "$output_int" -ne "$current_fan" ]; then
        set_fan_speed "$output_int"
    fi

    log "temp=${temp}°C err=${error} P=${p_term} I=${i_term} D=${d_term} → fan=${output_int}%"
}

cleanup() {
    log "Shutting down — restoring automatic fan control"
    set_fan_mode_auto
    rm -f "$HEARTBEAT"
    exit 0
}

trap cleanup SIGTERM SIGINT SIGHUP

# --- Main ---
log "Starting PID controller (setpoint=${SETPOINT}°C Kp=${KP} Ki=${KI} Kd=${KD})"

if ! nvidia-smi &>/dev/null; then
    log "ERROR: nvidia-smi not available"
    exit 1
fi

# Switch to manual fan control
set_fan_mode_manual

# Safety: start at 100% fan speed
set_fan_speed 100

while true; do
    date +%s > "$HEARTBEAT"

    temp=$(get_gpu_temp 2>/dev/null) || temp=""
    if [ -z "$temp" ]; then
        log "CRITICAL: Cannot read GPU temp — exiting to trigger watchdog"
        exit 1
    fi

    pid_step "$temp"

    sleep "$INTERVAL"
done
