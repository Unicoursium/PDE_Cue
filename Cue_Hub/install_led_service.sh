#!/bin/sh
set -eu

sudo cp /home/unico/matching_hub/cue-led.service /etc/systemd/system/cue-led.service
sudo systemctl daemon-reload
sudo systemctl enable --now cue-led.service
sudo systemctl status cue-led.service --no-pager
