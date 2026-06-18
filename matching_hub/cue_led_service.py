import json
import os
import socketserver
import fcntl
from pathlib import Path

from rpi_ws281x import Color, PixelStrip


SOCKET_PATH = os.environ.get("CUE_LED_SOCKET", "/run/cue-led.sock")
LOCK_PATH = os.environ.get("CUE_LED_LOCK", "/run/cue-led.lock")
LED_COUNT = int(os.environ.get("CUE_LED_COUNT", "55"))
LED_PIN = int(os.environ.get("CUE_LED_PIN", "18"))
LED_BRIGHTNESS = int(os.environ.get("CUE_LED_BRIGHTNESS", "60"))


class LedController:
    def __init__(self):
        self.strip = PixelStrip(
            LED_COUNT,
            LED_PIN,
            800000,
            10,
            False,
            LED_BRIGHTNESS,
            0,
        )
        self.strip.begin()
        self.clear()

    def set_pixels(self, pixels):
        for index in range(LED_COUNT):
            rgb = pixels.get(str(index), (0, 0, 0))
            self.strip.setPixelColor(index, Color(*rgb))
        self.strip.show()

    def clear(self):
        self.set_pixels({})


controller = None


class LedRequestHandler(socketserver.StreamRequestHandler):
    def handle(self):
        message = json.loads(self.rfile.readline())
        command = message.get("command")

        if command == "set_pixels":
            controller.set_pixels(message.get("pixels", {}))
        elif command == "clear":
            controller.clear()
        elif command != "ping":
            raise ValueError(f"Unknown LED command: {command}")


class LedServer(socketserver.UnixStreamServer):
    allow_reuse_address = True


def main():
    global controller

    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Another Cue LED service already owns GPIO18.")

    lock_file.write(str(os.getpid()))
    lock_file.flush()

    socket_path = Path(SOCKET_PATH)
    socket_path.unlink(missing_ok=True)
    controller = LedController()

    try:
        with LedServer(SOCKET_PATH, LedRequestHandler) as server:
            os.chmod(SOCKET_PATH, 0o666)
            print(f"Cue LED service listening on {SOCKET_PATH}")
            server.serve_forever()
    finally:
        controller.clear()
        socket_path.unlink(missing_ok=True)
        Path(LOCK_PATH).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
