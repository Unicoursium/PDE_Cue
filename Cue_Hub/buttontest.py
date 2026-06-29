import argparse
import time

from gpiozero import Button


LEFT_BUTTON_PIN = 23
RIGHT_BUTTON_PIN = 24
BOUNCE_TIME_SECONDS = 0.04


def run(left_pin, right_pin):
    left_button = Button(left_pin, pull_up=True, bounce_time=BOUNCE_TIME_SECONDS)
    right_button = Button(right_pin, pull_up=True, bounce_time=BOUNCE_TIME_SECONDS)

    print("Button test started.")
    print(f"LEFT button: GPIO{left_pin}")
    print(f"RIGHT button: GPIO{right_pin}")
    print("Press Ctrl+C to stop.")

    left_was_pressed = False
    right_was_pressed = False

    try:
        while True:
            left_pressed = left_button.is_pressed
            right_pressed = right_button.is_pressed

            if left_pressed and not left_was_pressed:
                print("LEFT pressed")
            if right_pressed and not right_was_pressed:
                print("RIGHT pressed")

            if not left_pressed and left_was_pressed:
                print("LEFT released")
            if not right_pressed and right_was_pressed:
                print("RIGHT released")

            left_was_pressed = left_pressed
            right_was_pressed = right_pressed
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nButton test stopped.")
    finally:
        left_button.close()
        right_button.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Test Cue left/right GPIO buttons.")
    parser.add_argument(
        "--left-pin",
        type=int,
        default=LEFT_BUTTON_PIN,
        help="BCM GPIO pin for the left button.",
    )
    parser.add_argument(
        "--right-pin",
        type=int,
        default=RIGHT_BUTTON_PIN,
        help="BCM GPIO pin for the right button.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    run(args.left_pin, args.right_pin)


if __name__ == "__main__":
    main()
