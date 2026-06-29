# `nfc_readers.py`

Purpose: dual PN532 NFC reader helper.

This file supports the kiosk's two-sided NFC scan flow.

## Reader Layout

- Left reader: PN532 over I2C using Raspberry Pi SDA/SCL.
- Right reader: PN532 over SPI using `board.SCK`, `board.MOSI`, `board.MISO`, and configurable CS, default `D8`.

## What It Reads

- NFC UID from passive target detection.
- Optional NTAG NDEF text/URI value.

The Android app writes RFID EPC into NFC tag NDEF text, so helper functions include NDEF TLV and text parsing.

## Key Functions

| Function | Purpose |
| --- | --- |
| `uid_to_hex()` | Converts UID bytes to uppercase hex. |
| `normalize_epc_value()` | Cleans EPC-like tag values. |
| `parse_ndef_tlv()` | Parses NFC TLV blocks and returns first NDEF value. |
| `DualPn532Readers.initialise()` | Creates left I2C and right SPI PN532 readers. |
| `DualPn532Readers.read_once()` | Returns left/right UID values. |
| `DualPn532Readers.read_once_with_values()` | Returns UID plus NDEF values. |
| `debounce_uid()` | Suppresses repeated scans of the same UID. |

