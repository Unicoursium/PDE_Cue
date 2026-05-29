from rpi_ws281x import PixelStrip, Color
import time

LED_COUNT = 120
LED_PIN = 18
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 50
LED_INVERT = False
LED_CHANNEL = 0

strip = PixelStrip(
    LED_COUNT,
    LED_PIN,
    LED_FREQ_HZ,
    LED_DMA,
    LED_INVERT,
    LED_BRIGHTNESS,
    LED_CHANNEL
)

strip.begin()

for i in range(LED_COUNT):
    strip.setPixelColor(i, Color(0, 0, 0))

strip.show()
time.sleep(0.5)
