# `cue_games.py`

Purpose: physical button + LED games.

This file implements games that mainly use the LED strip and physical buttons rather than a detailed screen UI.

## Games

| Game | Behavior |
| --- | --- |
| Tug of War | Players tap buttons to push the LED marker across `TUG_OF_WAR_PATH`. |
| Hot Potato | Players pass the "hot" side by pressing their button; whoever holds red at timeout loses. |
| Reaction Time | LEDs turn red, then green; fastest valid button press wins. Early presses give the point to the other player. |

## Hardware

- Left button: GPIO23.
- Right button: GPIO24.
- LEDs: through `PixelStrip` from `led_client.py`, which forwards to the LED service.

## Kiosk Integration

`cue_kiosk.py` calls `play_game()` for tug-of-war, hot potato, and reaction time. It passes existing button objects so the game does not need to reopen GPIO pins.

