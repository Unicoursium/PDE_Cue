# `R200_UHF_SCAN/r200_button_poll.py`

Purpose: legacy R200 polling test triggered by a button.

## Defaults

- Serial port: `/dev/ttyUSB0`.
- Baud: 115200.
- Button: GPIO23.
- Poll duration: 2 seconds.

When the button is pressed, the script sends inventory polling commands and prints R200 responses.

