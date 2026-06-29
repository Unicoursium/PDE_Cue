# `cue_led_service.py`

Purpose: single owner process for the WS281x LED strip.

The Raspberry Pi cannot safely have multiple processes driving GPIO18 for the LED strip. This service owns the strip and exposes a Unix socket API for other scripts.

## Defaults

| Setting | Default |
| --- | --- |
| Socket | `/run/cue-led.sock` |
| Lock file | `/run/cue-led.lock` |
| LED count | `55` |
| LED data GPIO | `18` |
| Brightness | `60` |

## Commands

The service accepts JSON lines over the Unix socket:

- `{"command": "set_pixels", "pixels": {"0": [255,0,0]}}`
- `{"command": "clear"}`
- `{"command": "ping"}`

## Used By

- `led_client.py`
- `cue_kiosk.py`
- `cue_games.py`
- `cue_screen_games.py`
- LED test scripts

