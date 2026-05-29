import time
import board
import neopixel

LED_COUNT = 10
LED_PIN = board.D18
BRIGHTNESS = 0.2

pixels = neopixel.NeoPixel(
    LED_PIN,
    LED_COUNT,
    brightness=BRIGHTNESS,
    auto_write=False,
    pixel_order=neopixel.GRB
)

pixels.fill((255, 0, 0))
pixels.show()
time.sleep(1)

pixels.fill((0, 255, 0))
pixels.show()
time.sleep(1)

pixels.fill((0, 0, 255))
pixels.show()
time.sleep(1)

pixels.fill((0, 0, 0))
pixels.show()
