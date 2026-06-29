# `virtualdj_soundcloud_automix.py`

Purpose: standalone VirtualDJ/SoundCloud Automix utility.

This file contains lower-level helpers for talking to VirtualDJ Network Control and converting SoundCloud URLs into track metadata.

## What It Does

- Resolves a SoundCloud URL into metadata.
- Connects to VirtualDJ Network Control.
- Searches VirtualDJ for a track.
- Reads selected browser results.
- Adds selected tracks to Automix.
- Starts Automix if needed.

## VirtualDJ Endpoints

The script uses:

- `/execute?script=...`
- `/query?script=...`

The base URL is configured with `VDJ_BASE_URL` or falls back to localhost ports.

## SoundCloud Handling

The script can read SoundCloud metadata and build search queries from artist/title information. It is mainly a utility/reference script now; the Android app stores SoundCloud metadata in Firestore for the formal flow.

