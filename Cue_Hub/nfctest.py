import argparse
import time

from nfc_readers import debounce_uid, parse_ndef_tlv, uid_to_hex


RIGHT_SPI_CS = "D8"
SCAN_TIMEOUT_SECONDS = 0.08


def create_left_reader():
    import board
    import busio
    from adafruit_pn532.i2c import PN532_I2C

    i2c = busio.I2C(board.SCL, board.SDA)
    reader = PN532_I2C(i2c, debug=False)
    reader.SAM_configuration()
    return reader


def create_right_reader(spi_cs):
    import board
    import busio
    import digitalio
    from adafruit_pn532.spi import PN532_SPI

    spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
    cs_pin = getattr(board, spi_cs)
    cs = digitalio.DigitalInOut(cs_pin)
    reader = PN532_SPI(spi, cs, debug=False)
    reader.SAM_configuration()
    return reader


def read_uid(reader, side, timeout):
    try:
        return uid_to_hex(reader.read_passive_target(timeout=timeout))
    except RuntimeError as error:
        print(f"{side} read error: {error}")
        try:
            reader.SAM_configuration()
        except RuntimeError as reconfigure_error:
            print(f"{side} reconfigure failed: {reconfigure_error}")
        return None


def read_ntag_value(reader, side, start_page=4, max_pages=40):
    data = bytearray()

    try:
        for page in range(start_page, start_page + max_pages):
            block = reader.ntag2xx_read_block(page)
            if block is None:
                break
            data.extend(block)
            if 0xFE in block:
                break
    except RuntimeError as error:
        print(f"{side} NDEF read error: {error}")
        return None

    return parse_ndef_tlv(bytes(data))


def initialise_reader(label, create_reader):
    try:
        reader = create_reader()
        print(f"{label}: OK")
        return reader
    except Exception as error:
        print(f"{label}: FAIL - {error}")
        return None


def run(spi_cs):
    print("Cue PN532 NFC test")
    print("LEFT  = I2C  SDA GPIO2 pin 3, SCL GPIO3 pin 5")
    print(f"RIGHT = SPI  CS {spi_cs}, SCK GPIO11 pin 23, MOSI GPIO10 pin 19, MISO GPIO9 pin 21")
    print()

    left_reader = initialise_reader("LEFT I2C PN532", create_left_reader)
    right_reader = initialise_reader(
        f"RIGHT SPI PN532 ({spi_cs})",
        lambda: create_right_reader(spi_cs),
    )

    if left_reader is None and right_reader is None:
        raise SystemExit("No PN532 readers initialised. Check wiring, power, and PN532 mode switches.")

    print()
    print("Scan a wristband/tag on either reader. Press Ctrl+C to stop.")

    last_left = (None, 0.0)
    last_right = (None, 0.0)

    try:
        while True:
            if left_reader is not None:
                left_uid = read_uid(left_reader, "LEFT", SCAN_TIMEOUT_SECONDS)
                last_left, left_new = debounce_uid(last_left, left_uid)
                if left_new:
                    value = read_ntag_value(left_reader, "LEFT")
                    print(f"LEFT NFC detected:  uid={left_uid}  value={value}")

            if right_reader is not None:
                right_uid = read_uid(right_reader, "RIGHT", SCAN_TIMEOUT_SECONDS)
                last_right, right_new = debounce_uid(last_right, right_uid)
                if right_new:
                    value = read_ntag_value(right_reader, "RIGHT")
                    print(f"RIGHT NFC detected: uid={right_uid}  value={value}")

            time.sleep(0.03)
    except KeyboardInterrupt:
        print("\nNFC test stopped.")


def parse_args():
    parser = argparse.ArgumentParser(description="Test both Cue PN532 NFC readers.")
    parser.add_argument(
        "--right-cs",
        default=RIGHT_SPI_CS,
        help="Board pin name for the right SPI PN532 chip select. Default: D8.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    run(args.right_cs)


if __name__ == "__main__":
    main()
