# `dual_servo_relay_test.py`

Purpose: token dispenser servo and relay sequence.

This script is both a test and the implementation called by `cue_kiosk.py` when dispensing a token.

## Defaults

| Component | GPIO | Movement |
| --- | --- | --- |
| Left servo | GPIO17 | 58 degrees to 10 degrees, then back to 58. |
| Right servo | GPIO25 | 132 degrees to 180 degrees, then back to 132. |
| Relay | GPIO22 | Pulses after 5 seconds for 0.5 seconds. |

## Notes

- Uses `gpiozero.AngularServo`.
- Uses `PiGPIOFactory`, so `pigpiod` should be running.
- Relay is active high.

