import time
import os
from glob import glob

import serial
from serial.tools import list_ports


PORT = os.environ.get("CUE_R200_PORT")
BAUD = 115200

INIT_COMMANDS = [
    bytes.fromhex("AA 00 07 00 01 01 09 DD"),
    bytes.fromhex("AA 00 AB 00 01 13 BF DD"),
    bytes.fromhex("AA 00 B6 00 02 0A 28 EA DD"),
]

POLL_COMMAND = bytes.fromhex("AA 00 22 00 00 22 DD")

SET_SELECT_MODE_ALL_OPERATIONS = bytes.fromhex("AA 00 12 00 01 00 13 DD")
SET_QUERY_SEL_SL = bytes.fromhex("AA 00 0E 00 02 1C 20 4C DD")
SELECTED_TAG_LED_COMMAND = bytes.fromhex(
    "AA 00 39 00 09 00 00 00 00 00 00 04 00 01 47 DD"
)


def hex_string(data):
    return " ".join(f"{byte:02X}" for byte in data)


def normalize_epc(epc):
    return (
        str(epc)
        .strip()
        .replace(" ", "")
        .replace(":", "")
        .replace("-", "")
        .upper()
    )


def build_frame(command, payload=b"", frame_type=0x00):
    payload_len = len(payload)
    frame_without_checksum = bytes(
        [
            0xAA,
            frame_type,
            command,
            (payload_len >> 8) & 0xFF,
            payload_len & 0xFF,
        ]
    ) + payload
    checksum = sum(frame_without_checksum[1:]) & 0xFF
    return frame_without_checksum + bytes([checksum, 0xDD])


def build_select_target_command(epc):
    epc_bytes = bytes.fromhex(normalize_epc(epc))

    # Existing tested command shape:
    # 81 00 00 00 20 60 00 <12-byte EPC>
    # This targets EPC memory starting at bit pointer 0x20 with bit length
    # matching the EPC byte length.
    bit_length = len(epc_bytes) * 8
    payload = bytes(
        [
            0x81,
            0x00,
            0x00,
            0x00,
            0x20,
            (bit_length >> 8) & 0xFF,
            bit_length & 0xFF,
        ]
    ) + epc_bytes

    return build_frame(command=0x0C, payload=payload)


def natural_port_key(port):
    return (
        port.replace("/dev/ttyUSB", "0:")
        .replace("/dev/ttyACM", "1:")
    )


def candidate_ports():
    if PORT:
        return [PORT]

    devices = []

    for port in list_ports.comports():
        if "ttyUSB" in port.device or "ttyACM" in port.device:
            devices.append(port.device)

    if not devices:
        devices = glob("/dev/ttyUSB*") + glob("/dev/ttyACM*")

    return sorted(set(devices), key=natural_port_key)


def split_frames(data):
    frames = []
    buffer = data

    while True:
        start = buffer.find(b"\xAA")
        if start == -1:
            break

        if start > 0:
            buffer = buffer[start:]

        if len(buffer) < 6:
            break

        payload_len = (buffer[3] << 8) | buffer[4]
        frame_len = 1 + 1 + 1 + 2 + payload_len + 1 + 1

        if len(buffer) < frame_len:
            break

        frame = buffer[:frame_len]

        if frame[-1] == 0xDD:
            frames.append(frame)

        buffer = buffer[frame_len:]

    return frames


def parse_frame(frame):
    if len(frame) < 7:
        return None

    if frame[0] != 0xAA or frame[-1] != 0xDD:
        return None

    frame_type = frame[1]
    command = frame[2]
    payload_len = (frame[3] << 8) | frame[4]
    payload = frame[5 : 5 + payload_len]
    checksum = frame[5 + payload_len]
    calculated_checksum = sum(frame[1 : 5 + payload_len]) & 0xFF

    if checksum != calculated_checksum:
        return {
            "type": "checksum_error",
            "raw": hex_string(frame),
        }

    if frame_type == 0x02 and command == 0x22:
        if len(payload) < 5:
            return None

        rssi_raw = payload[0]
        rssi = rssi_raw - 256 if rssi_raw > 127 else rssi_raw
        pc = payload[1:3].hex().upper()
        epc = payload[3:-2].hex().upper()
        crc = payload[-2:].hex().upper()

        return {
            "type": "tag",
            "rssi": rssi,
            "pc": pc,
            "epc": epc,
            "crc": crc,
        }

    if frame_type == 0x01 and command == 0xFF:
        error_code = payload[0] if payload else None
        return {
            "type": "error",
            "code": error_code,
        }

    return {
        "type": "response",
        "frame_type": frame_type,
        "command": command,
        "payload": payload.hex().upper(),
    }


class R200Reader:
    def __init__(self, port=None, baud=BAUD):
        self.port = port
        self.baud = baud
        self.ser = None

    def probe_port(self, port):
        try:
            with serial.Serial(port, self.baud, timeout=0.05) as probe:
                probe.reset_input_buffer()

                for cmd in INIT_COMMANDS:
                    probe.write(cmd)
                    probe.flush()

                    start = time.time()
                    response = b""
                    while time.time() - start < 0.15:
                        waiting = probe.in_waiting
                        if waiting:
                            response += probe.read(waiting)
                        time.sleep(0.005)

                    if split_frames(response):
                        return True

        except serial.SerialException as error:
            print(f"R200 probe skipped {port}: {error}")

        return False

    def detect_port(self):
        ports = candidate_ports()

        if not ports:
            print("No USB serial ports found for R200.")
            return None

        print(f"Probing R200 candidates: {', '.join(ports)}")

        for port in ports:
            if self.probe_port(port):
                print(f"R200 detected on {port}")
                return port

        print("No R200 response found on candidate ports.")
        return None

    def connect(self):
        while True:
            try:
                if self.port is None:
                    self.port = self.detect_port()

                    if self.port is None:
                        time.sleep(2)
                        continue

                self.ser = serial.Serial(self.port, self.baud, timeout=0.05)
                print(f"R200 connected on {self.port}")
                return
            except serial.SerialException as error:
                print(f"R200 not ready: {error}")
                if PORT is None:
                    self.port = None
                time.sleep(2)

    def close(self):
        if self.ser:
            self.ser.close()

    def send_and_read(self, cmd, read_time=0.08, log=False):
        self.ser.reset_input_buffer()

        if log:
            print(f">> {hex_string(cmd)}")

        self.ser.write(cmd)
        self.ser.flush()

        start = time.time()
        response = b""

        while time.time() - start < read_time:
            waiting = self.ser.in_waiting
            if waiting:
                response += self.ser.read(waiting)
            time.sleep(0.005)

        if log:
            if response:
                print(f"<< {hex_string(response)}")
            else:
                print("<< No response")

        return response

    def initialise(self):
        print("Initialising R200...")

        for cmd in INIT_COMMANDS:
            self.send_and_read(cmd, read_time=0.15, log=True)
            time.sleep(0.1)

        print("R200 initialised.")

    def inventory_once(self):
        response = self.send_and_read(POLL_COMMAND, read_time=0.08)
        frames = split_frames(response)
        tags = []

        for frame in frames:
            parsed = parse_frame(frame)
            if parsed and parsed["type"] == "tag":
                tags.append(parsed)

        return tags

    def select_epcs(self, epcs):
        normalized_epcs = [normalize_epc(epc) for epc in epcs if epc]

        print("Configuring R200 Select Mode...")
        self.initialise()

        for epc in normalized_epcs:
            print(f"Selecting EPC: {epc}")
            cmd = build_select_target_command(epc)
            self.send_and_read(cmd, read_time=0.12, log=True)
            time.sleep(0.1)

            print(f"Triggering selected tag LED: {epc}")
            self.send_and_read(SELECTED_TAG_LED_COMMAND, read_time=0.12, log=True)
            time.sleep(0.1)

        print("Applying Select before Inventory...")
        self.send_and_read(SET_SELECT_MODE_ALL_OPERATIONS, read_time=0.12, log=True)
        time.sleep(0.1)

        print("Setting Query Sel=SL...")
        self.send_and_read(SET_QUERY_SEL_SL, read_time=0.12, log=True)
        time.sleep(0.1)

        print("R200 Select Mode ready.")

    def select_epc_and_trigger_led(self, epc):
        normalized_epc = normalize_epc(epc)

        print(f"Selecting EPC for LED: {normalized_epc}")
        select_cmd = build_select_target_command(normalized_epc)
        self.send_and_read(select_cmd, read_time=0.08, log=True)
        time.sleep(0.04)

        print(f"Triggering selected tag LED: {normalized_epc}")
        self.send_and_read(SELECTED_TAG_LED_COMMAND, read_time=0.08, log=True)
