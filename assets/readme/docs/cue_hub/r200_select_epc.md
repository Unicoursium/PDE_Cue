# `R200_UHF_SCAN/r200_Select_EPC.py`

Purpose: legacy R200 select-EPC and wristband LED test.

This script configures the R200 to select a specific EPC and trigger the selected tag LED command.

## Defaults

- Serial port: `/dev/ttyUSB0`.
- Baud: 115200.
- Button: GPIO23.
- Target EPC is hardcoded in the script.

Use this for low-level R200 command debugging outside the main `matching_hub.py` runtime.

