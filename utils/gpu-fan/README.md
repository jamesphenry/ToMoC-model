# gpu-fan — PID fan control for Dell PowerEdge + passively cooled Tesla P4

A self-contained thermal governor for a **passively cooled NVIDIA Tesla P4 in a
Dell PowerEdge chassis**. The P4 has no fan of its own and relies on the server's
chassis fans. This overrides Dell BMC automatic fan control with a **PID
controller** that reads the GPU's *actual* thermal sensor (via `nvidia-smi`) and
drives the fans — something the BMC's auto mode cannot do, because it does not
see the GPU's internal temperature.

This is standalone homelab utility code (not part of tomac). Use at your own risk.

## Files

| File | Purpose |
|------|---------|
| `gpu-fan-control.sh` | PID controller (child). Reads GPU temp, sets fans via IPMI. |
| `gpu-fan-wrapper.sh` | Watchdog (parent). Restarts controller on death / stale heartbeat; fans to 100% on any fault. |
| `gpu-fan-control.service` | systemd unit (`Restart=always`, restores BMC AUTO on stop). |
| `DESIGN.md` | Design notes, the Dell BMC RPM-cap discovery, tuning, failure modes. |

## Requirements

- Dell PowerEdge with `ipmitool` (for the `0x30 0x30` raw fan commands)
- NVIDIA driver + `nvidia-smi` (`bc` for the float PID math)
- Root (the fan override and systemd unit need it)

## Install

```bash
sudo cp gpu-fan-control.sh gpu-fan-wrapper.sh /usr/local/bin/
sudo cp gpu-fan-control.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gpu-fan-control
```

## Uninstall / stop

```bash
sudo systemctl stop gpu-fan-control      # restores BMC automatic mode
sudo systemctl disable gpu-fan-control
```

## Tune

Edit `SETPOINT` / `KP` / `KI` / `KD` in `gpu-fan-control.sh`:

```bash
SETPOINT=67      # target GPU temp (°C)
KP="8.0"         # proportional gain (higher = more aggressive)
KI="0.5"         # integral gain (steady-state correction)
KD="2.0"         # derivative gain (dampening)
MIN_FAN=30       # never drop below this (%)
INTERVAL=10      # PID loop period (s)
```

The hard ceiling (80°C → unconditional 100%) is in `pid_step()`.

## Safety

- Watchdog restarts the controller within 5s of death, 30s of a stale heartbeat.
- Any fault → fans to 100% before deciding.
- Hard ceiling at 80°C forces 100% regardless of PID math.
- `ExecStopPost` restores BMC automatic mode on service stop.
- Power loss → BMC reverts to AUTO (hardware).

## Known limitations

Manual mode caps fan RPM at ~6,500 (BMC auto can reach 16,000+), so this trades
raw cooling headroom for GPU-sensor-aware control. At ~61W GPU draw the
equilibrium is ~80-88°C depending on workload; sustained sub-80°C may need better
chassis airflow. See `DESIGN.md` for the full analysis.

License: MIT.
