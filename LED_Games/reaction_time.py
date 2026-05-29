from rpi_ws281x import PixelStrip, Color
from gpiozero import Button
import time
import random

TOTAL_LEDS = 120
GAME_LEDS = 20

LED_PIN = 18
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 60
LED_INVERT = False
LED_CHANNEL = 0

LEFT_BUTTON_PIN = 23
RIGHT_BUTTON_PIN = 24

LEFT_COLOR = Color(255, 0, 255)     # Magenta
RIGHT_COLOR = Color(0, 255, 255)    # Cyan
RED = Color(255, 0, 0)
GREEN = Color(0, 255, 0)
WHITE = Color(255, 255, 255)
OFF = Color(0, 0, 0)

MIN_WAIT = 0.5
MAX_WAIT = 3.0

POLL_INTERVAL = 0.001

left_score = 0
right_score = 0

strip = PixelStrip(
    TOTAL_LEDS,
    LED_PIN,
    LED_FREQ_HZ,
    LED_DMA,
    LED_INVERT,
    LED_BRIGHTNESS,
    LED_CHANNEL
)

strip.begin()

left_button = Button(LEFT_BUTTON_PIN, pull_up=True, bounce_time=0.02)
right_button = Button(RIGHT_BUTTON_PIN, pull_up=True, bounce_time=0.02)


def set_all(color):
    for i in range(TOTAL_LEDS):
        strip.setPixelColor(i, OFF)

    for i in range(GAME_LEDS):
        strip.setPixelColor(i, color)

    strip.show()


def clear_all():
    for i in range(TOTAL_LEDS):
        strip.setPixelColor(i, OFF)
    strip.show()


def flash(color, times=5, delay=0.15):
    for _ in range(times):
        set_all(color)
        time.sleep(delay)
        set_all(OFF)
        time.sleep(delay)


def wait_for_buttons_released():
    while left_button.is_pressed or right_button.is_pressed:
        time.sleep(0.01)


def show_score():
    clear_all()

    for i in range(left_score):
        strip.setPixelColor(i, LEFT_COLOR)

    for i in range(right_score):
        strip.setPixelColor(GAME_LEDS - 1 - i, RIGHT_COLOR)

    strip.show()
    time.sleep(1.2)


def round_intro(round_number):
    print()
    print(f"Round {round_number}")
    print(f"Score: Left {left_score} - Right {right_score}")

    clear_all()
    time.sleep(0.3)

    for _ in range(2):
        set_all(WHITE)
        time.sleep(0.12)
        clear_all()
        time.sleep(0.12)


def play_round(round_number):
    round_intro(round_number)
    wait_for_buttons_released()

    set_all(RED)
    print("Red: wait...")

    wait_time = random.uniform(MIN_WAIT, MAX_WAIT)
    start_wait = time.monotonic()

    left_was_pressed = left_button.is_pressed
    right_was_pressed = right_button.is_pressed

    while time.monotonic() - start_wait < wait_time:
        left_now = left_button.is_pressed
        right_now = right_button.is_pressed

        if left_now and not left_was_pressed:
            print("Left pressed too early. Right wins this round.")
            flash(RIGHT_COLOR)
            wait_for_buttons_released()
            return "right", None, "early"

        if right_now and not right_was_pressed:
            print("Right pressed too early. Left wins this round.")
            flash(LEFT_COLOR)
            wait_for_buttons_released()
            return "left", None, "early"

        left_was_pressed = left_now
        right_was_pressed = right_now

        time.sleep(POLL_INTERVAL)

    set_all(GREEN)
    print("Green: GO!")

    green_time = time.monotonic()

    left_was_pressed = left_button.is_pressed
    right_was_pressed = right_button.is_pressed

    while True:
        now = time.monotonic()

        left_now = left_button.is_pressed
        right_now = right_button.is_pressed

        left_edge = left_now and not left_was_pressed
        right_edge = right_now and not right_was_pressed

        if left_edge and right_edge:
            print("Tie! Round replay.")
            flash(WHITE)
            wait_for_buttons_released()
            return "tie", None, "tie"

        if left_edge:
            reaction_time = now - green_time
            print(f"Left wins this round. Reaction time: {reaction_time:.3f}s")
            flash(LEFT_COLOR)
            wait_for_buttons_released()
            return "left", reaction_time, "normal"

        if right_edge:
            reaction_time = now - green_time
            print(f"Right wins this round. Reaction time: {reaction_time:.3f}s")
            flash(RIGHT_COLOR)
            wait_for_buttons_released()
            return "right", reaction_time, "normal"

        left_was_pressed = left_now
        right_was_pressed = right_now

        time.sleep(POLL_INTERVAL)


def final_winner():
    if left_score > right_score:
        print()
        print("LEFT PLAYER WINS THE GAME!")
        for _ in range(8):
            set_all(LEFT_COLOR)
            time.sleep(0.15)
            clear_all()
            time.sleep(0.15)
    else:
        print()
        print("RIGHT PLAYER WINS THE GAME!")
        for _ in range(8):
            set_all(RIGHT_COLOR)
            time.sleep(0.15)
            clear_all()
            time.sleep(0.15)


try:
    print("Reaction Time Game")
    print("Left button: GPIO23, Magenta")
    print("Right button: GPIO24, Cyan")
    print("First to 3 points wins. Best of 5.")
    print("Press Ctrl + C to stop.")

    clear_all()
    time.sleep(0.5)

    round_number = 1

    while left_score < 3 and right_score < 3 and round_number <= 5:
        winner, reaction, result_type = play_round(round_number)

        if winner == "left":
            left_score += 1
            round_number += 1
            show_score()

        elif winner == "right":
            right_score += 1
            round_number += 1
            show_score()

        elif winner == "tie":
            show_score()

    final_winner()
    time.sleep(2)
    clear_all()

except KeyboardInterrupt:
    clear_all()
    print()
    print("Game stopped.")
