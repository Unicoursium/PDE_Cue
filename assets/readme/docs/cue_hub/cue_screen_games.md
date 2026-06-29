# `cue_screen_games.py`

Purpose: Pygame screen-based games.

This file implements games that need active screen drawing in addition to buttons and LEDs.

## Games

| Game | Behavior |
| --- | --- |
| 5 Second Reaction | Each player tries to stop a timer closest to 5 seconds. |
| Darts | Players lock moving X/Y aim lines on a dartboard. Score starts at 151 and the first to exactly reach 0 wins. |
| Truth or Dare | Alternates truth/dare prompts between players. Holding both buttons skips or exits. |

## Hardware and UI

- Uses the kiosk's existing Pygame screen.
- Uses left/right physical buttons, with keyboard fallback in some helper functions.
- Uses LED side ranges to show active player or score.

## Kiosk Integration

`cue_kiosk.py` routes `five_second_reaction`, `darts`, and `truth_or_dare` through `play_screen_game()`.

