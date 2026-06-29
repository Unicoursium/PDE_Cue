# Cue_Hub Documentation

Source: `Cue_Hub`

`Cue_Hub` contains the Raspberry Pi code for the physical Cue hub: matching, R200 RFID scanning, PN532 NFC scanning, kiosk display, LED control, physical games, and token dispensing.

## Runtime Architecture

The Pi-side system is split into cooperating processes:

1. `cue_led_service.py` owns GPIO18 and the WS281x LED strip.
2. `matching_hub.py` watches Firestore profiles and the R200 RFID reader, creates Firestore matches, and lights matched wristbands.
3. `cue_kiosk.py` shows kiosk UI, waits for the two matched NFC wristbands, assigns games, runs games, and triggers token dispensing.

## Python File Index

| File | Document |
| --- | --- |
| `matching_hub.py` | [Firestore + R200 matching runtime](matching_hub.md) |
| `cue_kiosk.py` | [Kiosk UI, NFC scanning, game assignment](cue_kiosk.md) |
| `r200_reader.py` | [R200 UHF RFID protocol helper](r200_reader.md) |
| `nfc_readers.py` | [Dual PN532 NFC reader helper](nfc_readers.md) |
| `cue_led_service.py` | [LED strip service](cue_led_service.md) |
| `led_client.py` | [LED service client shim](led_client.md) |
| `led_layout.py` | [55 LED physical layout](led_layout.md) |
| `cue_games.py` | [Button + LED games](cue_games.md) |
| `cue_screen_games.py` | [Screen-based games](cue_screen_games.md) |
| `dual_servo_relay_test.py` | [Dual servo and relay token test](dual_servo_relay_test.md) |
| `servo_return_test.py` | [Single servo return test](servo_return_test.md) |
| `servo_sweep_test.py` | [Single servo sweep test](servo_sweep_test.md) |
| `solenoid_mosfet_test.py` | [Solenoid MOSFET test](solenoid_mosfet_test.md) |
| `buttontest.py` | [Left/right button test](buttontest.md) |
| `nfctest.py` | [Dual PN532 NFC test](nfctest.md) |
| `test_dual_pn532.py` | [Continuous dual PN532 test](test_dual_pn532.md) |
| `clear_cue_firestore.py` | [Firestore cleanup tool](clear_cue_firestore.md) |
| `prepare_clock_font.py` | [Clock font preparation](prepare_clock_font.md) |
| `R200_UHF_SCAN/r200_button_poll.py` | [Legacy R200 button polling test](r200_button_poll.md) |
| `R200_UHF_SCAN/r200_Select_EPC.py` | [Legacy R200 select-EPC test](r200_select_epc.md) |
| `Raspberry_pi_Tests/button_test.py` | [Early button test](raspberry_pi_tests_button_test.md) |
| `Raspberry_pi_Tests/led_test.py` | [Early LED service test](raspberry_pi_tests_led_test.md) |
| `Raspberry_pi_Tests/led_off.py` | [Early LED clear script](raspberry_pi_tests_led_off.md) |

## Hardware Reference

See [Cue Hub Hardware Wiring](../hardware/hardware_wiring.md) for GPIO, PN532, R200, LED, servo, and relay wiring.

