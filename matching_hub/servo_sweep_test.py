import argparse
import time

from gpiozero import AngularServo
from gpiozero.pins.pigpio import PiGPIOFactory


DEFAULT_GPIO_PIN = 17
DEFAULT_MIN_PULSE_WIDTH = 0.0007
DEFAULT_MAX_PULSE_WIDTH = 0.0023
START_ANGLE = 132
END_ANGLE = 180
RETURN_DELAY_SECONDS = 0.3


def sweep_servo(pin, delay, step, min_pulse_width, max_pulse_width):
    factory = PiGPIOFactory()
    servo = AngularServo(
        pin,
        min_angle=0,
        max_angle=180,
        min_pulse_width=min_pulse_width,
        max_pulse_width=max_pulse_width,
        pin_factory=factory,
    )

    try:
        print(
            f"Servo test on GPIO{pin} using pigpio. "
            f"Sweeping from {START_ANGLE} to {END_ANGLE} degrees."
        )
        print(
            "Pulse width range: "
            f"{min_pulse_width * 1000:.2f}ms - {max_pulse_width * 1000:.2f}ms"
        )
        servo.angle = START_ANGLE
        time.sleep(1)

        for angle in range(START_ANGLE, END_ANGLE + 1, step):
            print(f"Angle: {angle}")
            servo.angle = angle
            time.sleep(delay)

        print(
            f"Sweep complete. Holding at {END_ANGLE} degrees "
            f"for {RETURN_DELAY_SECONDS} seconds."
        )
        time.sleep(RETURN_DELAY_SECONDS)
        print(f"Returning to {START_ANGLE} degrees.")
        servo.angle = START_ANGLE
        time.sleep(delay)
    finally:
        servo.detach()
        servo.close()
        factory.close()
        print("Servo detached.")


def parse_args():
    parser = argparse.ArgumentParser(description="Slow 0-180 degree servo sweep test.")
    parser.add_argument(
        "--pin",
        type=int,
        default=DEFAULT_GPIO_PIN,
        help="BCM GPIO pin used for the servo signal wire.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.04,
        help="Delay between each angle step in seconds.",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=1,
        help="Angle increment per step.",
    )
    parser.add_argument(
        "--min-pulse-width",
        type=float,
        default=DEFAULT_MIN_PULSE_WIDTH,
        help="Minimum pulse width in seconds.",
    )
    parser.add_argument(
        "--max-pulse-width",
        type=float,
        default=DEFAULT_MAX_PULSE_WIDTH,
        help="Maximum pulse width in seconds.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    sweep_servo(
        args.pin,
        args.delay,
        args.step,
        args.min_pulse_width,
        args.max_pulse_width,
    )


if __name__ == "__main__":
    main()
