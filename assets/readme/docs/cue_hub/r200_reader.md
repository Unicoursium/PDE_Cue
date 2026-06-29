# `r200_reader.py`

Purpose: R200 UHF RFID reader protocol helper.

This file wraps the R200 serial protocol used by `matching_hub.py`.

## What It Does

- Auto-detects `/dev/ttyUSB*` and `/dev/ttyACM*` serial ports.
- Uses 115200 baud.
- Sends initialisation frames.
- Sends inventory polling frames.
- Splits and parses R200 frames.
- Extracts RFID tag RSSI, PC, EPC, and CRC.
- Builds select-target frames for a specific EPC.
- Sends the selected-tag LED command to light matched wristbands.

## Key Functions

| Function | Purpose |
| --- | --- |
| `normalize_epc()` | Removes separators and uppercases EPC values. |
| `build_frame()` | Builds R200 command frames with checksum. |
| `build_select_target_command()` | Builds EPC select command payload. |
| `split_frames()` | Extracts complete R200 frames from raw serial bytes. |
| `parse_frame()` | Converts frames into tag/error/response dictionaries. |
| `R200Reader.inventory_once()` | Polls once and returns detected tag dictionaries. |
| `R200Reader.select_epc_and_trigger_led()` | Selects one EPC and triggers its wristband LED. |

## Hardware

The R200 reader is connected over USB serial. Use `CUE_R200_PORT=/dev/ttyUSB0` to force a port; otherwise the code auto-probes.

