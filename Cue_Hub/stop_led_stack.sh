#!/bin/sh
set -eu

echo "Stopping cue-led.service..."
sudo systemctl stop cue-led.service 2>/dev/null || true

echo "Stopping LED-related Cue processes..."
sudo pkill -f "/home/unico/matching_hub/cue_led_service.py" 2>/dev/null || true
sudo pkill -f "/home/unico/matching_hub/cue_kiosk.py" 2>/dev/null || true
sudo pkill -f "/home/unico/matching_hub/cue_games.py" 2>/dev/null || true
sudo pkill -f "/home/unico/matching_hub/cue_screen_games.py" 2>/dev/null || true
sudo pkill -f "/home/unico/LED_Games/led_test.py" 2>/dev/null || true
sudo pkill -f "/home/unico/LED_Games/led_off.py" 2>/dev/null || true

echo "Removing LED socket and lock files..."
sudo rm -f /run/cue-led.sock /run/cue-led.lock

echo "Remaining LED service processes:"
pgrep -af "cue_led_service.py|cue_kiosk.py|cue_games.py|cue_screen_games.py|led_test.py|led_off.py" || true

echo "LED stack stopped."
