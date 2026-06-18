import argparse
import time

from gpiozero import AngularServo, OutputDevice
from gpiozero.pins.pigpio import PiGPIOFactory


LEFT_SERVO_GPIO_PIN = 17
RIGHT_SERVO_GPIO_PIN = 25
RELAY_GPIO_PIN = 22

LEFT_INITIAL_ANGLE = 58
LEFT_FINAL_ANGLE = 10
RIGHT_INITIAL_ANGLE = 132
RIGHT_FINAL_ANGLE = 180

STEP = 1
STEP_DELAY_SECONDS = 0.04
INITIAL_HOLD_SECONDS = 0.5
RETURN_HOLD_SECONDS = 0.5

MIN_PULSE_WIDTH = 0.0007
MAX_PULSE_WIDTH = 0.0023

RELAY_DELAY_SECONDS = 5.0
RELAY_ON_SECONDS = 0.5


def create_servo(pin, factory):
    return AngularServo(
        pin,
        min_angle=0,
        max_angle=180,
        min_pulse_width=MIN_PULSE_WIDTH,
        max_pulse_width=MAX_PULSE_WIDTH,
        pin_factory=factory,
    )


def interpolate(start, end, index, steps):
    if steps <= 0:
        return end
    return round(start + ((end - start) * index / steps))


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


def move_dual_servos(left_pin, right_pin, relay_pin):
    factory = PiGPIOFactory()
    left_servo = create_servo(left_pin, factory)
    right_servo = create_servo(right_pin, factory)

    try:
        print(
            f"Setting left servo GPIO{left_pin} to {LEFT_INITIAL_ANGLE} degrees "
            f"and right servo GPIO{right_pin} to {RIGHT_INITIAL_ANGLE} degrees."
        )
        left_servo.angle = LEFT_INITIAL_ANGLE
        right_servo.angle = RIGHT_INITIAL_ANGLE
        time.sleep(INITIAL_HOLD_SECONDS)

        print(
            "Sweeping both servos together: "
            f"left {LEFT_INITIAL_ANGLE}->{LEFT_FINAL_ANGLE}, "
            f"right {RIGHT_INITIAL_ANGLE}->{RIGHT_FINAL_ANGLE}."
        )
        steps = max(
            abs(LEFT_FINAL_ANGLE - LEFT_INITIAL_ANGLE),
            abs(RIGHT_FINAL_ANGLE - RIGHT_INITIAL_ANGLE),
        ) // abs(STEP)

        for index in range(steps + 1):
            left_angle = interpolate(LEFT_INITIAL_ANGLE, LEFT_FINAL_ANGLE, index, steps)
            right_angle = interpolate(RIGHT_INITIAL_ANGLE, RIGHT_FINAL_ANGLE, index, steps)
            print(f"Left: {left_angle}, Right: {right_angle}")
            left_servo.angle = left_angle
            right_servo.angle = right_angle
            time.sleep(STEP_DELAY_SECONDS)

        print(
            f"Returning immediately to left {LEFT_INITIAL_ANGLE} degrees "
            f"and right {RIGHT_INITIAL_ANGLE} degrees."
        )
        left_servo.angle = LEFT_INITIAL_ANGLE
        right_servo.angle = RIGHT_INITIAL_ANGLE
        time.sleep(RETURN_HOLD_SECONDS)

    finally:
        left_servo.detach()
        right_servo.detach()
        left_servo.close()
        right_servo.close()
        factory.close()
        print("Servos detached.")

    pulse_relay(relay_pin)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Sweep two servos together, return them, then pulse a relay."
    )
    parser.add_argument(
        "--left-pin",
        type=int,
        default=LEFT_SERVO_GPIO_PIN,
        help="BCM GPIO pin used for the left servo signal wire.",
    )
    parser.add_argument(
        "--right-pin",
        type=int,
        default=RIGHT_SERVO_GPIO_PIN,
        help="BCM GPIO pin used for the right servo signal wire.",
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
    move_dual_servos(args.left_pin, args.right_pin, args.relay_pin)


if __name__ == "__main__":
    main()
