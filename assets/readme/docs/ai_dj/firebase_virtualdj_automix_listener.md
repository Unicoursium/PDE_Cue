# `firebase_virtualdj_automix_listener.py`

Purpose: older profile-level listener that adds submitted SoundCloud tracks to VirtualDJ Automix.

This script is useful for preloading or testing a background Automix flow from Firestore profiles. It is not the main match-cue listener.

## What It Does

- Loads `.env` settings.
- Watches Firestore `profiles`.
- Looks for a configured track field, default `soundCloudTrack`.
- Searches VirtualDJ for each track.
- Adds the selected track to the Automix playlist.
- Marks profile documents with `aiDjAutomix.status`.
- Stores processed track keys in `processed_soundcloud_tracks.json`.

## VirtualDJ Protection

The script does not blindly add the first search result. It compares:

- SoundCloud ID against `netsearch://sc...` filepath.
- Cleaned title similarity.
- Artist similarity.

This reduces the risk of adding the wrong search result.

## Firestore Status Fields

On success:

```text
aiDjAutomix.status = ADDED_TO_AUTOMIX
```

On failure:

```text
aiDjAutomix.status = ERROR
aiDjAutomix.message = ...
```

## Relationship To Current Runtime

`cue_aidj_match_listener.py` reuses many helper functions from this file, including VirtualDJ connection and query functions.

