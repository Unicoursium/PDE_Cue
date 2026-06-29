# `servo_sweep_test.py`

Purpose: slow single-servo sweep test.

This script sweeps a servo from `START_ANGLE` to `END_ANGLE`, then returns to the start angle.

## Defaults

- Servo GPIO: GPIO17.
- Start angle: 132 degrees.
- End angle: 180 degrees.
- Uses `PiGPIOFactory` for stable PWM.

Use this for calibrating servo travel before running the dual-servo token sequence.

