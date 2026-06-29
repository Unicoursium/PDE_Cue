# `nfctest.py`

Purpose: dual PN532 NFC reader diagnostic.

This script checks both NFC modules and prints scan output.

## Wiring It Expects

- Left PN532: I2C, SDA GPIO2 pin 3, SCL GPIO3 pin 5.
- Right PN532: SPI, SCK GPIO11 pin 23, MOSI GPIO10 pin 19, MISO GPIO9 pin 21, CS D8 by default.

## What It Prints

- Whether each reader initialised successfully.
- UID values when wristbands/tags are scanned.
- NDEF text values when readable.

