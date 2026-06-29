# Cue

Cue is an interactive event matching system built for our PDE Group 18 project. The repository contains the source code for the Android app, Raspberry Pi matching hub, LED/button games, RFID/NFC readers, and the AI DJ computer-side integration used in the final prototype.

The project explores how a physical venue hub, wearable wristbands, a mobile onboarding flow, and music/game cues can work together to help people start conversations at an event.

## Contents

- [Repository Structure](#repository-structure)
- [Documentation Index](#documentation-index)
- [System Overview](#system-overview)
- [Portfolio](#portfolio)
- [Report](#report)

## Repository Structure

| Folder | Purpose |
| --- | --- |
| `android_apps/` | Android Studio workspace for Cue and supporting Android prototypes. The current Cue app handles onboarding, profile creation, local profile storage, pronunciation recording, SoundCloud song entry, Firebase upload, and NFC wristband scanning. |
| `Cue_Hub/` | Raspberry Pi hub runtime. This folder contains Firestore matching, R200 UHF RFID reading, dual PN532 NFC reading, kiosk screens, LED control, button games, screen games, token dispenser servo/relay tests, and hardware utility scripts. |
| `AI_DJ/` | Windows and VirtualDJ integration. It watches Firebase matches, plays matched users' SoundCloud tracks, announces names with text-to-speech, and uses uploaded pronunciation recordings when available. |
| `assets/` | README presentation assets and project documentation. `assets/readme/A3R` contains portfolio pages, `assets/readme/A4R` contains report pages, and `assets/readme/docs` contains code and hardware notes. |
| `LICENSE` | Project license. |

### Documentation Index

| Area | Documentation |
| --- | --- |
| Android app | [Cue Android App](assets/readme/docs/android/cue_android_app.md) |
| Raspberry Pi hub | [Cue_Hub Documentation](assets/readme/docs/cue_hub/index.md) |
| Hub hardware wiring | [Hardware Wiring](assets/readme/docs/hardware/hardware_wiring.md) |
| AI DJ | [AI_DJ Documentation](assets/readme/docs/ai_dj/index.md) |

## System Overview

Cue has three main runtime parts:

1. **Android app**: users create a profile, choose preferences, optionally record their name pronunciation, choose a song, and scan their wristband.
2. **Matching hub**: Firebase profiles are matched based on gender, orientation, age preferences, cue preferences, and game preferences. When a pair is detected in range, the hub lights their wristbands and guides them through the kiosk/game flow.
3. **AI DJ computer**: the venue computer reacts to matches by mixing the two users' selected songs or announcing their names with uploaded pronunciation recordings where possible.

## Portfolio

![Portfolio page 1](assets/readme/A3R/1.png)
![Portfolio page 2](assets/readme/A3R/2.png)
![Portfolio page 3](assets/readme/A3R/3.png)
![Portfolio page 4](assets/readme/A3R/4.png)
![Portfolio page 5](assets/readme/A3R/5.png)
![Portfolio page 6](assets/readme/A3R/6.png)
![Portfolio page 7](assets/readme/A3R/7.png)
![Portfolio page 8](assets/readme/A3R/8.png)
![Portfolio page 9](assets/readme/A3R/9.png)
![Portfolio page 10](assets/readme/A3R/10.png)
![Portfolio page 11](assets/readme/A3R/11.png)
![Portfolio page 12](assets/readme/A3R/12.png)
![Portfolio page 13](assets/readme/A3R/13.png)
![Portfolio page 14](assets/readme/A3R/14.png)
![Portfolio page 15](assets/readme/A3R/15.png)

## Report

![Report page 1](assets/readme/A4R/1.png)
![Report page 2](assets/readme/A4R/2.png)
![Report page 3](assets/readme/A4R/3.png)
![Report page 4](assets/readme/A4R/4.png)
![Report page 5](assets/readme/A4R/5.png)
![Report page 6](assets/readme/A4R/6.png)
![Report page 7](assets/readme/A4R/7.png)
![Report page 8](assets/readme/A4R/8.png)
![Report page 9](assets/readme/A4R/9.png)
![Report page 10](assets/readme/A4R/10.png)
![Report page 11](assets/readme/A4R/11.png)
![Report page 12](assets/readme/A4R/12.png)
![Report page 13](assets/readme/A4R/13.png)
![Report page 14](assets/readme/A4R/14.png)
![Report page 15](assets/readme/A4R/15.png)
![Report page 16](assets/readme/A4R/16.png)
![Report page 17](assets/readme/A4R/17.png)
![Report page 18](assets/readme/A4R/18.png)
![Report page 19](assets/readme/A4R/19.png)
![Report page 20](assets/readme/A4R/20.png)
![Report page 21](assets/readme/A4R/21.png)
![Report page 22](assets/readme/A4R/22.png)
