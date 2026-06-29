import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "matching_hub"))

from led_client import LedClient


LedClient().clear()
print("Cue LED strip cleared through cue-led.service.")
