import serial
import time
from gpiozero import Button

PORT = "/dev/ttyUSB0"
BAUD = 115200

BUTTON_GPIO = 23

TARGET_EPC = "E2004711A7B06426A9050110"

INIT_COMMANDS = [
    bytes.fromhex("AA 00 07 00 01 01 09 DD"),
    bytes.fromhex("AA 00 AB 00 01 13 BF DD"),
    bytes.fromhex("AA 00 B6 00 02 0A 28 EA DD"),
]

SET_SELECT_TARGET = bytes.fromhex(
    "AA 00 0C 00 13 81 00 00 00 20 60 00 "
    "E2 00 47 11 A7 B0 64 26 A9 05 01 10 FA DD"
)

SET_SELECT_MODE_ALL_OPERATIONS = bytes.fromhex(
    "AA 00 12 00 01 00 13 DD"
)

SET_QUERY_SEL_SL = bytes.fromhex(
    "AA 00 0E 00 02 1C 20 4C DD"
)

POLL_COMMAND = bytes.fromhex("AA 00 22 00 00 22 DD")

POLL_DURATION = 200.0
POLL_INTERVAL = 0.1

ser = serial.Serial(PORT, BAUD, timeout=0.05)
button = Button(BUTTON_GPIO, pull_up=True, bounce_time=0.05)


def hex_string(data):
    return " ".join(f"{b:02X}" for b in data)


def send_and_read(cmd, read_time=0.12):
    ser.reset_input_buffer()

    print(f">> {hex_string(cmd)}")
    ser.write(cmd)
    ser.flush()

    start = time.time()
    response = b""

    while time.time() - start < read_time:
        waiting = ser.in_waiting
        if waiting:
            response += ser.read(waiting)
        time.sleep(0.005)

    if response:
        print(f"<< {hex_string(response)}")
    else:
        print("<< No response")

    return response


def split_frames(data):
    frames = []
    buffer = data

    while True:
        start = buffer.find(b"\xAA")
        if start == -1:
            break

        if len(buffer) < start + 6:
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
    payload = frame[5:5 + payload_len]
    checksum = frame[5 + payload_len]

    calculated_checksum = sum(frame[1:5 + payload_len]) & 0xFF

    if checksum != calculated_checksum:
        return {
            "type": "checksum_error",
            "raw": hex_string(frame),
        }

    if frame_type == 0x02 and command == 0x22:
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


def configure_target_select():
    print("Initialising R200...")

    for cmd in INIT_COMMANDS:
        send_and_read(cmd)
        time.sleep(0.1)

    print("\nSetting Select target EPC...")
    send_and_read(SET_SELECT_TARGET)
    time.sleep(0.1)

    print("\nSetting Select mode: apply Select before Inventory...")
    send_and_read(SET_SELECT_MODE_ALL_OPERATIONS)
    time.sleep(0.1)

    print("\nSetting Query Sel=SL...")
    send_and_read(SET_QUERY_SEL_SL)
    time.sleep(0.1)

    print("\nConfiguration finished.")
    print(f"Target EPC: {TARGET_EPC}")
    print("Press button on GPIO23 to check target tag.")


def check_target():
    print("\nChecking selected target tag...")

    found = False
    poll_count = 0
    end_time = time.time() + POLL_DURATION

    while time.time() < end_time:
        poll_count += 1

        response = send_and_read(POLL_COMMAND, read_time=0.08)
        frames = split_frames(response)

        for frame in frames:
            parsed = parse_frame(frame)

            if not parsed:
                continue

            if parsed["type"] == "tag":
                epc = parsed["epc"]
                rssi = parsed["rssi"]

                print(f"Poll {poll_count}: EPC={epc}, RSSI={rssi} dBm")

                if epc == TARGET_EPC:
                    found = True

            elif parsed["type"] == "error":
                if parsed["code"] == 0x15:
                    print(f"Poll {poll_count}: no selected tag response")
                else:
                    print(f"Poll {poll_count}: error code 0x{parsed['code']:02X}")

        time.sleep(POLL_INTERVAL)

    if found:
        print("\nResult: TARGET PRESENT\n")
    else:
        print("\nResult: TARGET ABSENT\n")


try:
    configure_target_select()

    while True:
        button.wait_for_press()
        check_target()
        button.wait_for_release()

except KeyboardInterrupt:
    print("\nStopped by user.")

finally:
    ser.close()
