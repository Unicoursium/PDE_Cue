import json
import os
import socket


SOCKET_PATH = os.environ.get("CUE_LED_SOCKET", "/run/cue-led.sock")


def Color(red, green, blue):
    return int(red), int(green), int(blue)


class LedClient:
    def __init__(self, socket_path=SOCKET_PATH):
        self.socket_path = socket_path

    def send(self, command):
        payload = (json.dumps(command, separators=(",", ":")) + "\n").encode()

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(0.5)
            connection.connect(self.socket_path)
            connection.sendall(payload)

    def set_pixels(self, pixels):
        self.send(
            {
                "command": "set_pixels",
                "pixels": {
                    str(index): list(color)
                    for index, color in pixels.items()
                },
            }
        )

    def clear(self):
        self.send({"command": "clear"})

    def ping(self):
        self.send({"command": "ping"})


class PixelStrip:
    """Small rpi_ws281x-compatible adapter used by the existing games."""

    def __init__(self, count, *args, **kwargs):
        del args, kwargs
        self.count = count
        self.pixels = {index: (0, 0, 0) for index in range(count)}
        self.last_pixels = None
        self.client = LedClient()

    def begin(self):
        self.client.ping()

    def setPixelColor(self, index, color):
        if 0 <= index < self.count:
            self.pixels[index] = tuple(color)

    def show(self):
        if self.pixels == self.last_pixels:
            return
        self.client.set_pixels(self.pixels)
        self.last_pixels = self.pixels.copy()
