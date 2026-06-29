# `led_client.py`

Purpose: client compatibility layer for `cue_led_service.py`.

This file provides a small API that resembles the `rpi_ws281x` `PixelStrip` interface while actually sending pixel commands to the LED service socket.

## Important Classes

| Class | Purpose |
| --- | --- |
| `LedClient` | Sends JSON commands to `/run/cue-led.sock`. |
| `PixelStrip` | Compatibility wrapper with `setPixelColor()` and `show()`. |

## Why It Exists

Games and kiosk code can update LEDs without directly owning GPIO18. This avoids conflicts between the kiosk, games, and service processes.

