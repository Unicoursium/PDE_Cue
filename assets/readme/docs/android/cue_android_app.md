# Cue Android App

Source: `android_apps/Cue`

The Cue Android app is the participant-facing mobile experience. It is implemented as a single Jetpack Compose activity backed by Firebase Firestore and Firebase Storage.

## Main Responsibilities

- Shows the Cue splash, intro, saved-profile, onboarding, profile-complete, and wristband-scan screens.
- Collects profile data: name, gender/identity, sexual orientation, age, desired match age range, hub cue preference, game/help preference, optional socials, and optional SoundCloud song.
- Records an optional name pronunciation clip locally as `.m4a` using Android `MediaRecorder`.
- Uploads pronunciation audio to Firebase Storage under `pronunciations/...`.
- Uploads profile data to Firestore `profiles`.
- Reads a wristband NFC tag and uploads both NFC UID and the NDEF text value, which stores the RFID EPC.
- Saves the most recently submitted profile locally in SharedPreferences so returning users can skip the questionnaire and proceed directly to wristband scanning.

## Important Folders

| Path | Purpose |
| --- | --- |
| `app/src/main/java/com/example/cue/` | Kotlin source. `MainActivity.kt` contains the app flow, Firebase upload logic, SoundCloud search, NFC reading, and Compose UI. |
| `app/src/main/java/com/example/cue/ui/theme/` | Compose theme files, including Cue font families and color/theme setup. |
| `app/src/main/res/drawable/` | Cue logos, social icons, SoundCloud icon, NFC/wristband graphics, and completed-state artwork used by the onboarding UI. |
| `app/src/main/res/font/` | Project fonts: Koulen for headings and Inter Light for smaller interface text. |
| `app/src/main/res/mipmap-*` | App launcher icons. |
| `app/src/main/res/values/` | Android resource values such as strings, colors, and themes. |
| `gradle/` | Gradle wrapper and version catalog. |

## Key Files

| File | Purpose |
| --- | --- |
| `app/src/main/AndroidManifest.xml` | Declares NFC, Internet, and record-audio permissions. NFC is marked as not required so the app can still install on devices without NFC. |
| `app/build.gradle.kts` | Android module configuration. Enables Compose, Firebase, and BuildConfig values for SoundCloud credentials read from `local.properties`. |
| `app/google-services.json` | Firebase Android app configuration for the project. |
| `firestore.rules` | Firestore security rules used during development/testing. |
| `storage.rules` | Firebase Storage rules used during development/testing. |
| `firebase.json` | Firebase project configuration file. |

## Firestore Profile Shape

The app writes documents to `profiles` with fields used by the matching hub and AI DJ:

| Field | Meaning |
| --- | --- |
| `status` | Starts as `ONBOARDING_SUBMITTED`; becomes `WRISTBAND_SCANNED` after NFC wristband upload. |
| `name`, `nickname` | Participant name. |
| `gender`, `identity`, `identityOther` | Gender/identity response. |
| `orientation`, `lookingFor`, `orientationOther` | Sexual orientation response. |
| `age` | Participant age. |
| `matchAgeRange.min`, `matchAgeRange.max` | Desired age range. |
| `cueChoice` | Hub cue preference: song, name calling, or either. |
| `matchedPreference` | Post-match preference, stored as the exact long option text from the questionnaire. |
| `soundCloudTrack` | Optional selected SoundCloud track object. |
| `pronunciation` | Optional recording metadata with `fileName`, `localPath`, `storagePath`, and `downloadUrl`. In the current implementation, `downloadUrl` may be null; AI_DJ can use `storagePath`. |
| `socials` | Optional Instagram, Snapchat, and WhatsApp fields. |
| `nfcUid`, `rfidEpc`, `wristband` | Added after wristband scan. The NFC NDEF value is treated as the RFID EPC. |

## App Flow

1. Splash screen fades out.
2. Intro explainer appears.
3. If a previous profile exists locally, the app shows the saved profile page.
4. If no saved profile exists, the questionnaire starts.
5. User submits profile, optionally including pronunciation audio and SoundCloud track.
6. Profile complete page lets the user proceed to event scanning or exit.
7. Wristband scan reads NFC UID and RFID EPC value, uploads them to the matching profile, then exits or shows completion.

## SoundCloud Integration

The app uses SoundCloud client credentials from `local.properties`:

```properties
soundcloud.client.id=...
soundcloud.client.secret=...
```

The Kotlin code obtains an OAuth token with the client-credentials flow, searches tracks, resolves pasted SoundCloud links, and stores selected track metadata in Firestore.

## NFC Wristband Reading

`MainActivity` enables Android reader mode when a scan screen is active. On tag discovery, it reads:

- `tag.id` as the NFC UID.
- First NDEF text record as the RFID EPC value.

If either value is missing, the app asks the user to scan again instead of uploading incomplete wristband data.
