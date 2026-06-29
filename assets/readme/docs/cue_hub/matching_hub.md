# `matching_hub.py`

Purpose: Raspberry Pi matching runtime.

This script connects Firestore profile data to physical R200 RFID presence detection. It creates match documents and triggers matched wristband LEDs through the R200 reader.

## What It Does

- Uses Firebase Admin SDK with `serviceAccountKey.json`.
- Watches Firestore `profiles` where `status == WRISTBAND_SCANNED`.
- Caches ready users by RFID EPC.
- Polls the R200 UHF RFID reader for nearby EPCs.
- Adds detected ready users into an "entered range" cache.
- Finds compatible pairs.
- Writes a `matches/{matchId}` document.
- Updates both profile documents to `status = MATCHED`.
- Repeatedly selects matched EPCs and sends the R200 selected-tag LED command.
- Listens on `/tmp/cue-matching-hub.sock` for kiosk reset commands.

## Matching Inputs

The script expects these profile fields from the Android app:

- `gender` or `identity`
- `orientation` or `lookingFor`
- `age`
- `matchAgeRange.min`
- `matchAgeRange.max`
- `cueChoice`
- `matchedPreference`
- `nfcUid`
- `rfidEpc`
- optional `soundCloudTrack`
- optional `pronunciation`

## Matching Rules

Users are compatible when:

- Each user is interested in the other's gender based on orientation.
- Both users fall within each other's desired age range.
- Cue choices match, or either user selected `EITHER`.
- Matched preferences are compatible:
  - no help only matches no help.
  - longer game only matches longer game.
  - small ice breaker and short game can match each other.

## Firestore Output

Creates `matches/{matchId}` with:

- `status`
- `createdAt`
- `profileIds`
- `rfidEpcs`
- `nfcUids`
- `users`
- `cueChoice`
- `matchedPreference`

The user payload includes `soundCloudTrack` and `pronunciation` so AIDJ can react to the match.

## Hardware Dependency

Uses `R200Reader` from `r200_reader.py`. The R200 is connected over USB serial and auto-detected from `/dev/ttyUSB*` or `/dev/ttyACM*`, unless `CUE_R200_PORT` is set.

