import time


URI_PREFIXES = [
    "",
    "http://www.",
    "https://www.",
    "http://",
    "https://",
]


def uid_to_hex(uid):
    if not uid:
        return None
    return "".join(f"{byte:02X}" for byte in uid)


def normalize_epc_value(value):
    if value is None:
        return None
    return (
        value.strip()
        .replace(" ", "")
        .replace("-", "")
        .replace(":", "")
        .replace("=", "")
        .upper()
        .removeprefix("RFID")
        .removeprefix("UHF")
        .removeprefix("EPC")
    )


def parse_text_payload(payload):
    if not payload:
        return None

    status = payload[0]
    language_length = status & 0x3F
    encoding = "utf-8" if status & 0x80 == 0 else "utf-16"
    text_start = 1 + language_length

    if len(payload) <= text_start:
        return None

    return payload[text_start:].decode(encoding, errors="replace").strip() or None


def parse_uri_payload(payload):
    if not payload:
        return None

    prefix = URI_PREFIXES[payload[0]] if payload[0] < len(URI_PREFIXES) else ""
    body = payload[1:].decode("utf-8", errors="replace")
    return (prefix + body).strip() or None


def parse_ndef_record(record):
    if len(record) < 3:
        return None

    header = record[0]
    short_record = bool(header & 0x10)
    type_length = record[1]

    if short_record:
        if len(record) < 3 + type_length:
            return None
        payload_length = record[2]
        payload_start = 3 + type_length
        record_type = record[3:payload_start]
    else:
        if len(record) < 6 + type_length:
            return None
        payload_length = int.from_bytes(record[2:6], "big")
        payload_start = 6 + type_length
        record_type = record[6:payload_start]

    payload_end = payload_start + payload_length
    if len(record) < payload_end:
        return None

    payload = record[payload_start:payload_end]

    if record_type == b"T":
        return parse_text_payload(payload)
    if record_type == b"U":
        return parse_uri_payload(payload)

    return payload.decode("utf-8", errors="replace").strip() or None


def parse_ndef_tlv(data):
    index = 0

    while index < len(data):
        tag_type = data[index]
        index += 1

        if tag_type == 0x00:
            continue
        if tag_type == 0xFE:
            return None
        if index >= len(data):
            return None

        length = data[index]
        index += 1

        if length == 0xFF:
            if index + 2 > len(data):
                return None
            length = int.from_bytes(data[index:index + 2], "big")
            index += 2

        value = data[index:index + length]
        index += length

        if tag_type == 0x03:
            return parse_ndef_record(value)

    return None


class DualPn532Readers:
    def __init__(self, spi_cs="D8"):
        self.spi_cs = spi_cs
        self.left = None
        self.right = None

    def initialise(self):
        import board
        import busio
        import digitalio
        from adafruit_pn532.i2c import PN532_I2C
        from adafruit_pn532.spi import PN532_SPI

        i2c = busio.I2C(board.SCL, board.SDA)
        self.left = PN532_I2C(i2c, debug=False)
        self.left.SAM_configuration()

        spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        cs_pin = getattr(board, self.spi_cs)
        cs = digitalio.DigitalInOut(cs_pin)
        self.right = PN532_SPI(spi, cs, debug=False)
        self.right.SAM_configuration()

        print("PN532 readers ready: LEFT=I2C 0x24, RIGHT=SPI CS " + self.spi_cs)

    def read_uid(self, reader, side, timeout=0.05):
        try:
            return uid_to_hex(reader.read_passive_target(timeout=timeout))
        except RuntimeError as error:
            print(f"{side} PN532 read error: {error}. Reconfiguring...")
            try:
                reader.SAM_configuration()
            except RuntimeError as reconfigure_error:
                print(f"{side} PN532 reconfigure failed: {reconfigure_error}")
            return None

    def read_ntag_ndef_value(self, reader, side, start_page=4, max_pages=40):
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
            print(f"{side} PN532 NDEF read error: {error}. Reconfiguring...")
            try:
                reader.SAM_configuration()
            except RuntimeError as reconfigure_error:
                print(f"{side} PN532 reconfigure failed: {reconfigure_error}")
            return None

        return parse_ndef_tlv(bytes(data))

    def read_left_uid(self, timeout=0.05):
        return self.read_uid(self.left, "LEFT", timeout=timeout)

    def read_right_uid(self, timeout=0.05):
        return self.read_uid(self.right, "RIGHT", timeout=timeout)

    def read_left_value(self):
        return self.read_ntag_ndef_value(self.left, "LEFT")

    def read_right_value(self):
        return self.read_ntag_ndef_value(self.right, "RIGHT")

    def read_once(self, timeout=0.05):
        return {
            "left": self.read_left_uid(timeout=timeout),
            "right": self.read_right_uid(timeout=timeout),
        }

    def read_once_with_values(self, timeout=0.05):
        left_uid = self.read_left_uid(timeout=timeout)
        right_uid = self.read_right_uid(timeout=timeout)

        return {
            "left": {
                "uid": left_uid,
                "value": self.read_left_value() if left_uid else None,
            },
            "right": {
                "uid": right_uid,
                "value": self.read_right_value() if right_uid else None,
            },
        }


def debounce_uid(last_uid, uid, min_interval=0.8, repeat_same_uid=False):
    now = time.monotonic()

    if uid is None:
        return last_uid, False

    previous_uid, previous_time = last_uid
    if uid == previous_uid and not repeat_same_uid:
        return last_uid, False

    if uid == previous_uid and now - previous_time < min_interval:
        return last_uid, False

    return (uid, now), True
