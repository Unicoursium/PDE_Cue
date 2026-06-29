# Cue Hub Hardware Wiring

This document summarises the hardware connections used by the Raspberry Pi hub code in `Cue_Hub`.

All GPIO numbers below use **BCM numbering**, matching the Python scripts.

## Core Raspberry Pi Connections

| Hardware | GPIO / Interface | Notes |
| --- | --- | --- |
| WS281x LED strip data | GPIO18 | Controlled by `cue_led_service.py`; default count is 55 LEDs. |
| Left player button | GPIO23 | Used by kiosk and games. Buttons are configured with `pull_up=True`, so wire the button between GPIO and GND. |
| Right player button | GPIO24 | Same wiring pattern as left button. |
| Left token servo signal | GPIO17 | Used by `dual_servo_relay_test.py` and token dispensing from kiosk. |
| Right token servo signal | GPIO25 | Used by `dual_servo_relay_test.py`. |
| Token relay input | GPIO22 | Driven high to trigger relay after servo movement. |
| Optional solenoid MOSFET test | GPIO27 | Used only by `solenoid_mosfet_test.py`. |
| R200 UHF RFID reader | USB serial, usually `/dev/ttyUSB*` or `/dev/ttyACM*` | Auto-detected by `r200_reader.py`; can be forced with `CUE_R200_PORT`. |
| Left PN532 NFC reader | I2C: SDA GPIO2 pin 3, SCL GPIO3 pin 5 | Used by `nfc_readers.py` and `nfctest.py`. |
| Right PN532 NFC reader | SPI: SCK GPIO11 pin 23, MOSI GPIO10 pin 19, MISO GPIO9 pin 21, CS D8 | Chip select is configurable with `CUE_RIGHT_PN532_CS`. |

## LED Layout

The physical strip has 55 LEDs and is represented in code with zero-based indexes.

| Physical section | Human numbering | Code indexes |
| --- | --- | --- |
| Left half, top to bottom | 9 to 35 | 8 to 34 |
| Center LED | 36 | 35 |
| Right half, top to bottom | 8 to 1, then 55 to 37 | 7 to 0, then 54 to 36 |

`led_layout.py` defines:

- `LEFT_SIDE`
- `RIGHT_SIDE`
- `CENTER_LED`
- `TUG_OF_WAR_PATH`
- `score_leds(side, count)`

The tug-of-war game uses one continuous path from the left top, down to the center LED, then up the right side.

## PN532 Reader Layout

The kiosk uses two NFC readers:

- Left side: PN532 over I2C.
- Right side: PN532 over SPI with CS D8 by default.

The NFC UID is used to identify which participant scanned. The Android app writes the RFID EPC into the NFC tag as an NDEF text value; the Pi-side NFC tools can also read NDEF values for testing.

## R200 RFID Reader

The R200 reader is handled over serial at 115200 baud. The code:

1. Probes `/dev/ttyUSB*` and `/dev/ttyACM*`.
2. Sends initialisation frames.
3. Polls tag inventory frames.
4. Parses EPC, RSSI, PC, and CRC values.
5. Selects matched EPCs and sends the selected-tag LED command to light wristbands.

## Token Dispenser

The token sequence is shared by `dual_servo_relay_test.py` and kiosk token dispensing:

1. Move left servo from 58 degrees to 10 degrees.
2. Move right servo from 132 degrees to 180 degrees.
3. Return both servos to their initial positions.
4. Wait 5 seconds.
5. Pulse GPIO22 relay for 0.5 seconds.

The servo code uses `gpiozero.AngularServo` with `PiGPIOFactory`, so the Pi should have `pigpiod` running for stable servo pulses.
