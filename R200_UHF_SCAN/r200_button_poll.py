import serial
import time
from gpiozero import Button

PORT = "/dev/ttyUSB0"
BAUD = 115200

BUTTON_GPIO = 23

INIT_COMMANDS = [
    bytes.fromhex("AA 00 07 00 01 01 09 DD"),
    bytes.fromhex("AA 00 AB 00 01 13 BF DD"),
    bytes.fromhex("AA 00 B6 00 02 0A 28 EA DD"),
]

POLL_COMMAND = bytes.fromhex("AA 00 22 00 00 22 DD")

POLL_DURATION = 2.0
POLL_INTERVAL = 0.1

ser = serial.Serial(PORT, BAUD, timeout=0.05)

button = Button(BUTTON_GPIO, pull_up=True, bounce_time=0.05)


def hex_string(data):
    return " ".join(f"{b:02X}" for b in data)


def send_and_read(cmd, read_time=0.08):
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


def initialise_reader():
    print("Initialising R200...")

    for cmd in INIT_COMMANDS:
        send_and_read(cmd, read_time=0.15)
        time.sleep(0.1)

    print("Initialisation finished.")
    print("Press button on GPIO23 to start 2-second polling.")


def poll_for_2_seconds():
    print("\nButton pressed. Start polling for 2 seconds...")

    end_time = time.time() + POLL_DURATION
    count = 0

    while time.time() < end_time:
        count += 1
        print(f"\nPoll {count}")
        send_and_read(POLL_COMMAND, read_time=0.08)
        time.sleep(POLL_INTERVAL)

    print("Polling finished.\n")


try:
    initialise_reader()

    while True:
        button.wait_for_press()
        poll_for_2_seconds()
        button.wait_for_release()

except KeyboardInterrupt:
    print("\nStopped by user.")

finally:
    ser.close()
