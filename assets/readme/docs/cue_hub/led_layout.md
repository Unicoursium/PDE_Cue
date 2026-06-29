# `led_layout.py`

Purpose: physical LED layout mapping for the 55 LED hub.

The code uses zero-based LED indexes, but comments document the human one-based positions.

## Layout

- Left side top-to-bottom: human LEDs 9 to 35, code indexes 8 to 34.
- Center LED: human LED 36, code index 35.
- Right side top-to-bottom: human LEDs 8 to 1, then 55 to 37, code indexes 7 to 0 then 54 to 36.

## Exports

| Name | Purpose |
| --- | --- |
| `LED_COUNT` | Total LEDs, 55. |
| `CENTER_LED` | Center LED index, 35. |
| `LEFT_SIDE` | Left side indexes top-to-bottom. |
| `RIGHT_SIDE` | Right side indexes top-to-bottom. |
| `TUG_OF_WAR_PATH` | Continuous game path through left, center, and right sides. |
| `score_leds(side, count)` | Returns bottom-outward LEDs for score/progress displays. |

