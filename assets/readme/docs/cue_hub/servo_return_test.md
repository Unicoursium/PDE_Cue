# `servo_return_test.py`

Purpose: single-servo return sequence with relay pulse.

The script waits, moves one servo from its initial angle to final angle, returns it to initial angle, then pulses the relay.

## Defaults

- Servo GPIO: GPIO17.
- Initial angle: 58 degrees.
- Final angle: 10 degrees.
- Start delay: 10 seconds.
- Relay GPIO: GPIO22.
- Relay delay: 3 seconds.

Use this when testing one side of the token mechanism.

