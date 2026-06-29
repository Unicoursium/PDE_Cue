# `cue_kiosk.py`

Purpose: Raspberry Pi kiosk runtime.

This script owns the visible 640x480 kiosk flow and coordinates NFC scanning, LED feedback, game assignment, game launch, and token dispensing.

## What It Does

- Opens a Pygame display.
- Shows a Cue clock while idle.
- Listens for `MATCHED` Firestore documents.
- When a match arrives, shows the "scan respective wristbands" page.
- Reads left and right NFC readers.
- Checks that scanned NFC UIDs belong to the current match.
- Updates hub LEDs:
  - pulsing pink while waiting.
  - solid pink on the side already scanned.
- Assigns games from the users' `matchedPreference` values.
- Runs LED games from `cue_games.py` or screen games from `cue_screen_games.py`.
- Shows coupon/game-over screens.
- Calls `dual_servo_relay_test.move_dual_servos()` to dispense a token.
- Sends `RESET` to the matching hub socket after a game.

## Inputs

- Firestore `matches` collection.
- Dual PN532 readers from `nfc_readers.py`.
- Left/right buttons on GPIO23 and GPIO24.
- LED service through `led_client.py`.
- Kiosk image assets from `Cue_Hub/assets`.

## Game Assignment

| Matched preference combination | Result |
| --- | --- |
| no help + no help | Show coupon page, no game. |
| small ice breaker + small ice breaker | Random short/light game with shorter settings. |
| small ice breaker + short game | Random short/light game with medium settings. |
| short game + short game | Random short/light game with longer settings. |
| longer game + longer game | Random long game: darts or truth-or-dare. |

## Debug Mode

While on the clock screen, holding both buttons for 3 seconds enters debug scan mode. This creates a fake match so PN532 scanning can be tested without a Firestore match.

## Important Environment Variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `CUE_KIOSK_WIDTH` | `640` | Kiosk display width. |
| `CUE_KIOSK_HEIGHT` | `480` | Kiosk display height. |
| `CUE_KIOSK_FULLSCREEN` | `1` | Borderless fullscreen-like display. |
| `CUE_KIOSK_DISPLAY_INDEX` | `0` | Pygame display index. |
| `CUE_KIOSK_NFC_ENABLED` | `1` | Enables PN532 scanning. |
| `CUE_LEFT_BUTTON_PIN` | `23` | Left button GPIO. |
| `CUE_RIGHT_BUTTON_PIN` | `24` | Right button GPIO. |
| `CUE_RIGHT_PN532_CS` | `D8` | SPI chip select for right PN532. |
| `CUE_TOKEN_LEFT_SERVO_PIN` | `17` | Left token servo signal. |
| `CUE_TOKEN_RIGHT_SERVO_PIN` | `25` | Right token servo signal. |
| `CUE_TOKEN_RELAY_PIN` | `22` | Token relay input. |

