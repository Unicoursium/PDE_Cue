# `aidj_two_deck_16s_demo.py`

Purpose: manual two-deck VirtualDJ cue demo.

This script was used to prototype the two-song match cue before wiring it to Firebase matches.

## What It Does

- Searches two tracks in VirtualDJ.
- Loads track A to deck 1 and track B to deck 2.
- Alternates playback between decks.
- Crossfades between tracks.
- Stops both decks when done or when a safety segment limit is reached.

## Default Demo Tracks

- `Glitchery Heavenly Key`
- `2hollis Poster Boy`

These can be changed with command-line arguments.

## Relationship To Formal AIDJ

`cue_aidj_match_listener.py` imports deck helpers from this file:

- `search_and_load_to_deck`
- `deck_is_finished`
- `set_deck_volume`
- `stop_all_decks`

