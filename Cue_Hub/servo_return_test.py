import argparse
import time

from gpiozero import AngularServo, OutputDevice
from gpiozero.pins.pigpio import PiGPIOFactory


GPIO_PIN = 17
INITIAL_ANGLE = 58
FINAL_ANGLE = 10
START_DELAY_SECONDS = 10.0
STEP = 1
STEP_DELAY_SECONDS = 0.04
RETURN_HOLD_SECONDS = 0.5
MIN_PULSE_WIDTH = 0.0007
MAX_PULSE_WIDTH = 0.0023
RELAY_GPIO_PIN = 22
RELAY_DELAY_SECONDS = 3.0
RELAY_ON_SECONDS = 0.5


def pulse_relay(pin):
    relay = OutputDevice(pin, active_high=True, initial_value=False)

    try:
        print(
            f"Waiting {RELAY_DELAY_SECONDS:.1f}s, then enabling relay "
            f"on GPIO{pin} for {RELAY_ON_SECONDS:.1f}s."
        )
        time.sleep(RELAY_DELAY_SECONDS)
        relay.on()
        time.sleep(RELAY_ON_SECONDS)
        relay.off()
    finally:
        relay.off()
        relay.close()
        print("Relay GPIO disabled.")


def move_servo(pin, relay_pin):
    factory = PiGPIOFactory()
    servo = AngularServo(
        pin,
        min_angle=0,
        max_angle=180,
        min_pulse_width=MIN_PULSE_WIDTH,
        max_pulse_width=MAX_PULSE_WIDTH,
        pin_factory=factory,
    )

    try:
        print(f"Setting servo on GPIO{pin} to initial angle {INITIAL_ANGLE} degrees.")
        servo.angle = INITIAL_ANGLE
        time.sleep(RETURN_HOLD_SECONDS)

        print(f"Waiting {START_DELAY_SECONDS:.1f}s before starting sweep.")
        time.sleep(START_DELAY_SECONDS)

        print(
            f"Servo on GPIO{pin}: slowly sweeping "
            f"{INITIAL_ANGLE} -> {FINAL_ANGLE}, then returning to {INITIAL_ANGLE}."
        )

        direction = -1 if FINAL_ANGLE < INITIAL_ANGLE else 1
        step = abs(STEP) * direction

        for angle in range(INITIAL_ANGLE, FINAL_ANGLE + direction, step):
            print(f"Angle: {angle}")
            servo.angle = angle
            time.sleep(STEP_DELAY_SECONDS)

        print(f"Returning directly to {INITIAL_ANGLE} degrees.")
        servo.angle = INITIAL_ANGLE
        time.sleep(RETURN_HOLD_SECONDS)

    finally:
        servo.detach()
        servo.close()
        factory.close()
        print("Servo detached.")

    pulse_relay(relay_pin)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Move a servo from INITIAL_ANGLE to FINAL_ANGLE and back."
    )
    parser.add_argument(
        "--pin",
        type=int,
        default=GPIO_PIN,
        help="BCM GPIO pin used for the servo signal wire.",
    )
    parser.add_argument(
        "--relay-pin",
        type=int,
        default=RELAY_GPIO_PIN,
        help="BCM GPIO pin connected to the relay input.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    move_servo(args.pin, args.relay_pin)


if __name__ == "__main__":
    main()