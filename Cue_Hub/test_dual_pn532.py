import os
import time

from nfc_readers import DualPn532Readers, debounce_uid


SPI_CS = os.environ.get("CUE_RIGHT_PN532_CS", "D8")


def main():
    readers = DualPn532Readers(spi_cs=SPI_CS)
    readers.initialise()

    print("Scanning both PN532 readers.")
    print("Press Ctrl+C to stop.")

    last_left = (None, 0.0)
    last_right = (None, 0.0)

    while True:
        seen = readers.read_once_with_values(timeout=0.05)

        left_uid = seen["left"]["uid"]
        right_uid = seen["right"]["uid"]

        last_left, left_new = debounce_uid(last_left, left_uid)
        last_right, right_new = debounce_uid(last_right, right_uid)

        if left_new:
            print(
                f"LEFT NFC:  uid={left_uid} "
                f"value={seen['left']['value']}"
            )
        if right_new:
            print(
                f"RIGHT NFC: uid={right_uid} "
                f"value={seen['right']['value']}"
            )

        time.sleep(0.03)


if __name__ == "__main__":
    main()
