import argparse
import time

from gpiozero import OutputDevice


DEFAULT_GPIO_PIN = 27
DEFAULT_PULSE_SECONDS = 0.05
DEFAULT_COOLDOWN_SECONDS = 1.0


def fire_solenoid(pin, pulse_seconds, cooldown_seconds, repeats):
    trigger = OutputDevice(pin, active_high=True, initial_value=False)

    try:
        print(
            f"Solenoid MOSFET test on GPIO{pin}. "
            f"Pulse={pulse_seconds:.3f}s repeats={repeats}"
        )

        for index in range(repeats):
            print(f"Pulse {index + 1}/{repeats}: ON")
            trigger.on()
            time.sleep(pulse_seconds)
            trigger.off()
            print("OFF")

            if index < repeats - 1:
                time.sleep(cooldown_seconds)
    finally:
        trigger.off()
        trigger.close()
        print("GPIO output disabled.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Short pulse test for a MOSFET-switched solenoid."
    )
    parser.add_argument(
        "--pin",
        type=int,
        default=DEFAULT_GPIO_PIN,
        help="BCM GPIO pin connected to the MOSFET gate resistor.",
    )
    parser.add_argument(
        "--pulse",
        type=float,
        default=DEFAULT_PULSE_SECONDS,
        help="MOSFET on-time in seconds.",
    )
    parser.add_argument(
        "--cooldown",
        type=float,
        default=DEFAULT_COOLDOWN_SECONDS,
        help="Delay between repeated pulses in seconds.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Number of pulses to fire.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.pulse <= 0:
        raise ValueError("--pulse must be greater than 0")
    if args.repeats < 1:
        raise ValueError("--repeats must be at least 1")

    fire_solenoid(args.pin, args.pulse, args.cooldown, args.repeats)


if __name__ == "__main__":
    main()
