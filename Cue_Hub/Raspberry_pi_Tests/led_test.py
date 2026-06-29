import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "matching_hub"))

from led_client import LedClient


LED_COUNT = 40
client = LedClient()

for color in ((255, 0, 0), (0, 255, 0), (0, 0, 255)):
    client.set_pixels({index: color for index in range(LED_COUNT)})
    time.sleep(1)

client.clear()
print("Cue LED service test completed.")
