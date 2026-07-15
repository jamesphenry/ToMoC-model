# GPU Fan Control for Dell PowerEdge + Tesla P4
> License: MIT (same as tomac repo).

## The Problem

A passively cooled NVIDIA Tesla P4 in a Dell PowerEdge server has no fan of its own.
It relies entirely on the server's chassis fans for cooling. Under GPU compute load
(98% util, ~50-60W), the P4 can reach 88-92°C — dangerously close to thermal
throttling.

## Key Discovery: Dell BMC Manual Mode Fan Cap

Dell PowerEdge BMC firmware hard-caps manual fan duty cycle at approximately 6,500 RPM.
The raw IPMI command `0x30 0x30 0x02 0xff 0x64` (all fans, 100% duty) produces
~6,500 RPM regardless of the percentage sent. This is a firmware limitation, not a
software bug. The cap exists as a safety feature.

By contrast, the BMC's automatic mode can ramp all 14 fans (7A + 7B) to 16,000+ RPM
using its own thermal algorithm — which considers inlet temperature, exhaust temperature,
PCIe zone sensors, and power consumption data.

However, the BMC auto mode does **not** directly read the NVIDIA GPU's internal thermal
sensor. The Tesla P4's temperature is only visible to the NVIDIA driver (via NVML).
This means the BMC's auto algorithm may not respond fast enough to GPU-specific heat.

## Our Solution: PID Controller + Watchdog

A PID (Proportional-Integral-Derivative) controller in manual IPMI mode provides
direct, predictable fan speed control based on the GPU's actual temperature — something
the BMC auto mode cannot do since it doesn't read GPU thermal sensors.

### Why PID over threshold control?

A simple threshold controller (if temp > X then set fans to Y%) causes oscillation:
fans ramp up, GPU cools, fans drop, GPU heats up, repeat. A PID controller produces
smooth, continuous fan speed changes that settle at the correct speed for the current
thermal load.

### PID Parameters

| Param | Value | Behavior |
|-------|-------|----------|
| Setpoint | 67°C | Target GPU temperature |
| Kp | 8.0 | Per 1°C above setpoint → +8% fan speed |
| Ki | 0.5 | Slow integral to eliminate steady-state error |
| Kd | 2.0 | Dampening to prevent oscillation |
| Min fan | 30% | Floor — never go below this |
| Max fan | 100% | Ceiling |
| Hard ceiling | 80°C | If GPU >= 80°C, override PID to 100% |
| Sample interval | 10s | PID loop period |

### PID Behavior

```
Error = current_temp - setpoint (positive when too hot)

At 86°C: error=19, P=152 → clamped to 100% by hard ceiling
At 80°C: error=13, P=104 → clamped to 100% by hard ceiling
At 78°C: error=11, P=88 + integral(wound) → 100% fans
At 73°C: error=6, P=48 + integral(wound under sustained load) → 100% fans
At 67°C: error=0, P=0 → integral holds ~30% floor (idle/light load)
Below 67°C: negative error → integral winds down → 30% floor
Note: under sustained GPU load the integral term winds up to its anti-windup cap,
so duty typically pegs 100% whenever temp sits above setpoint for long — that is
expected (it is holding the setpoint, not oscillating).
```

### Safety Features

- **Anti-windup**: Integral term clamped to prevent runaway when output saturates
- **Hard ceiling**: 80°C triggers unconditional 100% override — no PID math, no debate
- **Failed temp read**: Script exits immediately, watchdog sets 100% fans
- **30% floor**: Fans never go below 30% (maintains baseline airflow for passive GPU)
- **IPMI failure**: Script exits immediately, watchdog catches it

## Watchdog Architecture

A two-process design ensures fans are never left at a dangerous speed.

```
gpu-fan-control.service (systemd, Type=simple)
└── gpu-fan-wrapper.sh (watchdog, PID 1)
    ├── Step 1: Switch to manual mode, set fans to 100% (safety first)
    ├── Step 2: Fork gpu-fan-control.sh as child process
    ├── Monitor loop (every 5s):
    │   ├── Is child alive? → restart if dead
    │   ├── Is heartbeat fresh? → restart if stale >30s
    │   └── After restart: set fans to 100% before child starts
    └── On service stop (SIGTERM):
        ├── Kill child process
        ├── Restore BMC automatic fan control
        └── Clean up heartbeat file

ExecStopPost (systemd): restores BMC auto mode as final fallback
```

### Why a wrapper and not just the PID script?

The wrapper is ~40 lines of bash with zero dependencies on nvidia-smi or floating-point
math. It has virtually zero crash surface. If the PID controller crashes (IPMI error,
nvidia-smi failure, arithmetic error), the wrapper catches it within 5 seconds and
sets fans to 100%.

### Failure Modes

| Failure                      | Response                                  |
|------------------------------|-------------------------------------------|
| PID controller crashes       | Watchdog restarts within 5s, fans at 100% |
| PID controller hangs         | Watchdog detects stale heartbeat within 30s, kills + restarts |
| nvidia-smi fails             | PID exits 1 → watchdog catches it         |
| IPMI command fails           | PID exits 1 → watchdog catches it         |
| Service stopped cleanly      | ExecStopPost restores BMC auto mode       |
| Power loss                   | BMC reverts to auto on PowerEdge (hardware) |

## Known Limitations

1. **Manual mode caps at ~6,500 RPM** — BMC auto mode can reach 16,000+ RPM.
   Our manual override produces less maximum airflow than the BMC's own algorithm.
   The PID approach trades raw cooling power for precise GPU-temperature-based control.

2. **BMC auto mode doesn't read GPU temp** — The BMC uses inlet/exhaust/PCIe zone
   sensors. It may not respond to GPU-specific heat quickly enough. Our PID controller
   reads the GPU's actual thermal sensor via nvidia-smi.

3. **Physical cooling ceiling** — At ~61W GPU draw with ~6,500 RPM fans, the thermal
   equilibrium is approximately 80-88°C depending on workload. For sustained sub-80°C,
   physical improvements (better airflow, additional fans) may be needed.

## Files

| File | Purpose |
|------|---------|
| `/usr/local/bin/gpu-fan-control.sh` | PID controller (child process) |
| `/usr/local/bin/gpu-fan-wrapper.sh` | Watchdog wrapper (parent process) |
| `/etc/systemd/system/gpu-fan-control.service` | Systemd unit file |

## Tuning

Adjust in `gpu-fan-control.sh`:

```bash
SETPOINT=67      # Target GPU temperature (°C)
KP="8.0"         # Proportional gain (higher = more aggressive)
KI="0.5"         # Integral gain (higher = faster steady-state correction)
KD="2.0"         # Derivative gain (higher = more dampening)
MIN_FAN=30       # Minimum fan speed (%)
INTERVAL=10      # Loop interval (seconds)
```

Hard ceiling is hardcoded at 80°C in the `pid_step()` function. Change the
`if [ "$temp" -ge 80 ]` line to adjust.

## Commands

```bash
# Status
systemctl status gpu-fan-control
journalctl -u gpu-fan-control -f

# Stop (restores BMC auto mode)
systemctl stop gpu-fan-control

# Check BMC fan speeds
ipmitool sensor list | grep -i fan

# Check GPU temp
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader
```
