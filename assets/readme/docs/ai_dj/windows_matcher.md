# `windows_matcher.py`

Purpose: temporary Windows-side matcher for demos when the Raspberry Pi hub is not available.

This script listens to Android-created Firestore profiles and creates `matches` documents directly from Windows.

## What It Does

- Connects to Firestore with Firebase Admin SDK.
- Watches the `profiles` collection.
- Accepts profiles with statuses from `CUE_WINDOWS_MATCH_PROFILE_STATUSES`, defaulting to `ONBOARDING_SUBMITTED,WRISTBAND_SCANNED`.
- Normalises gender, sexual orientation, age range, cue choice, and matched preference.
- Finds the first compatible pair.
- Writes a `matches/{matchId}` document.
- Updates both matched profiles to `status = MATCHED`.

## Matching Rules

Two users match only when:

- Each user's orientation accepts the other's gender.
- Each user's age is inside the other's desired age range.
- Hub cue choices are compatible:
  - same choice, or
  - either user selected `EITHER`.
- Matched preferences are compatible:
  - no help matches no help only.
  - longer game matches longer game only.
  - small ice breaker and short game can match with each other.

## Firestore Output

The match payload includes:

- `profileIds`
- `rfidEpcs`
- `nfcUids`
- `users`
- `cueChoice`
- `matchedPreference`
- `source: windows_matcher`

Each user payload carries `soundCloudTrack` and `pronunciation`, so `cue_aidj_match_listener.py` can play songs or recorded names.

## When To Use

Use this when testing Android + AIDJ without the physical Raspberry Pi/R200 setup.

