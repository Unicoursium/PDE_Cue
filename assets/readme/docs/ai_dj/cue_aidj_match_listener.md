# `cue_aidj_match_listener.py`

Purpose: formal AI DJ runtime for matched Cue pairs.

This script is the main Windows-side AIDJ process. It loads a background playlist into VirtualDJ Automix, listens to Firestore `matches`, and reacts when a match reaches `MATCHED`.

## What It Does

- Loads `.env` settings from `AI_DJ/.env`.
- Connects to VirtualDJ Network Control.
- Loads `aidj_playlist.txt` into the Automix side view.
- Watches the Firestore `matches` collection.
- Skips match IDs already stored in `processed_aidj_matches.json`.
- For two-song matches:
  - Searches VirtualDJ for each user's SoundCloud track.
  - Loads user A onto deck 1 and user B onto deck 2.
  - Plays ABAB, 8 seconds each by default.
  - Uses a 2 second overlap crossfade between segments by default.
- For name-call matches:
  - Uses pronunciation recordings when present.
  - Falls back to Windows TTS for missing or failed recordings.

## Firestore Input

The script expects a match document shaped like:

```text
matches/{matchId}
  status: MATCHED
  users: [
    {
      profileId,
      name,
      soundCloudTrack,
      pronunciation
    },
    ...
  ]
```

`soundCloudTrack.url` enables the two-song cue. `pronunciation.storagePath` or `pronunciation.downloadUrl` enables recorded name playback.

## Pronunciation Playback

The Android app may store `downloadUrl = null`, so the script supports two download paths:

1. Use `pronunciation.downloadUrl` when available.
2. Use Firebase Admin SDK with `AIDJ_STORAGE_BUCKET` and `pronunciation.storagePath`.

Downloaded audio is cached in `.pronunciation_cache`. The audio is played through Windows WPF `MediaPlayer`, which can handle the Android `.m4a` files.

## VirtualDJ Control

The script imports helper functions from:

- `firebase_virtualdj_automix_listener.py`
- `aidj_two_deck_16s_demo.py`

It uses VirtualDJ `/execute` and `/query` Network Control endpoints to search, load decks, play/pause, set volume, and control Automix.

## Useful Settings

| Setting | Default | Meaning |
| --- | --- | --- |
| `AIDJ_MATCH_SEGMENT_SECONDS` | `8` | Segment time for each deck. |
| `AIDJ_MATCH_FADE_SECONDS` | `2` | Crossfade overlap time. |
| `AIDJ_MATCH_AB_REPEATS` | `2` | AB pair count; `2` gives ABAB. |
| `AIDJ_TTS_ENABLED` | `1` | Enables Windows text-to-speech. |
| `AIDJ_PRONUNCIATION_ENABLED` | `1` | Enables downloaded pronunciation audio. |

## Notes

- Restart the script after changing `.env`.
- Clear `processed_aidj_matches.json` to replay old matches during testing.
- If VirtualDJ search returns the wrong track, inspect the stored `soundCloudTrack` metadata and VirtualDJ NetSearch result.

