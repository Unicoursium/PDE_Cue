# AI_DJ Documentation

Source: `AI_DJ`

The AI_DJ folder contains Windows-side tools that connect Firebase profile/match data to VirtualDJ. It supports background Automix playback, match-triggered two-song cues, text-to-speech name calls, and pronunciation recording playback.

## Runtime Requirements

- Windows computer running VirtualDJ.
- VirtualDJ Network Control enabled.
- Python dependencies from `AI_DJ/requirements.txt`.
- Firebase service account JSON, normally placed at `AI_DJ/serviceAccountKey.json` or configured with `FIREBASE_SERVICE_ACCOUNT`.
- `.env` configuration based on `.env.example`.

## Python File Index

| File | Document |
| --- | --- |
| `cue_aidj_match_listener.py` | [Formal matched-pair AIDJ listener](cue_aidj_match_listener.md) |
| `windows_matcher.py` | [Windows fallback matcher](windows_matcher.md) |
| `firebase_virtualdj_automix_listener.py` | [Profile-to-Automix listener](firebase_virtualdj_automix_listener.md) |
| `virtualdj_soundcloud_automix.py` | [VirtualDJ and SoundCloud helper script](virtualdj_soundcloud_automix.md) |
| `aidj_two_deck_16s_demo.py` | [Two-deck cue demo](aidj_two_deck_16s_demo.md) |

## Important Data Flow

1. Android app uploads profiles to Firestore.
2. Matching code writes `matches/{matchId}` documents.
3. `cue_aidj_match_listener.py` watches for `status == MATCHED`.
4. If both users have `soundCloudTrack`, it loads their tracks to VirtualDJ decks A/B and plays ABAB with overlap crossfade.
5. If song cue is unavailable, it announces names with TTS and optional uploaded pronunciation recordings.

## Configuration

Important `.env` keys:

| Key | Purpose |
| --- | --- |
| `FIREBASE_SERVICE_ACCOUNT` | Path to Firebase Admin SDK service account JSON. |
| `VDJ_BASE_URL` | VirtualDJ Network Control endpoint, usually `http://127.0.0.1:8080`. |
| `AIDJ_MATCHES_COLLECTION` | Firestore collection for matches. Default: `matches`. |
| `AIDJ_MATCH_STATUS` | Match status to react to. Default: `MATCHED`. |
| `AIDJ_MATCH_SEGMENT_SECONDS` | Per-song cue segment length. Current default: `8`. |
| `AIDJ_MATCH_FADE_SECONDS` | Overlap crossfade length. Current default: `2`. |
| `AIDJ_MATCH_AB_REPEATS` | Number of AB repeats. Current default: `2`, producing ABAB. |
| `AIDJ_STORAGE_BUCKET` | Firebase Storage bucket used to download pronunciation recordings by `storagePath`. |
| `AIDJ_PRONUNCIATION_ENABLED` | Enables pronunciation audio playback before falling back to TTS. |

