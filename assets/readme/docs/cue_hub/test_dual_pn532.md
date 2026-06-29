# `test_dual_pn532.py`

Purpose: minimal continuous dual PN532 test.

This script imports `DualPn532Readers`, initialises both readers, and continuously scans them. It is smaller than `nfctest.py` and useful when checking only the shared helper class.

Default right reader chip select is controlled by `CUE_RIGHT_PN532_CS`, default `D8`.

