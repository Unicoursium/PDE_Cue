from rpi_ws281x import PixelStrip, Color
from gpiozero import Button
import time
import random

TOTAL_LEDS = 120
GAME_LEDS = 20

LEFT_START = 0
LEFT_END = 9
RIGHT_START = 10
RIGHT_END = 19

LED_PIN = 18
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 60
LED_INVERT = False
LED_CHANNEL = 0

LEFT_BUTTON_PIN = 23
RIGHT_BUTTON_PIN = 24

HOT_COLOR = Color(255, 0, 0)
SAFE_COLOR = Color(0, 255, 0)
WHITE = Color(255, 255, 255)
YELLOW = Color(255, 180, 0)
OFF = Color(0, 0, 0)

GAME_TIME = 30.0
POLL_INTERVAL = 0.01

hot_side = random.choice(["left", "right"])

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

left_button = Button(LEFT_BUTTON_PIN, pull_up=True, bounce_time=0.04)
right_button = Button(RIGHT_BUTTON_PIN, pull_up=True, bounce_time=0.04)


def clear_all():
    for i in range(TOTAL_LEDS):
        strip.setPixelColor(i, OFF)
    strip.show()


def set_half(start, end, color):
    for i in range(start, end + 1):
        strip.setPixelColor(i, color)


def show_sides():
    for i in range(TOTAL_LEDS):
        strip.setPixelColor(i, OFF)

    if hot_side == "left":
        set_half(LEFT_START, LEFT_END, HOT_COLOR)
        set_half(RIGHT_START, RIGHT_END, SAFE_COLOR)
    else:
        set_half(LEFT_START, LEFT_END, SAFE_COLOR)
        set_half(RIGHT_START, RIGHT_END, HOT_COLOR)

    strip.show()


def show_timer_progress(elapsed):
    progress = max(0.0, min(1.0, elapsed / GAME_TIME))

    off_per_side = int(((GAME_LEDS // 2) - 1) * progress)

    for i in range(TOTAL_LEDS):
        strip.setPixelColor(i, OFF)

    if hot_side == "left":
        left_color = HOT_COLOR
        right_color = SAFE_COLOR
    else:
        left_color = SAFE_COLOR
        right_color = HOT_COLOR

    left_visible_start = LEFT_START
    left_visible_end = LEFT_END - off_per_side

    right_visible_start = RIGHT_START + off_per_side
    right_visible_end = RIGHT_END

    if left_visible_start <= left_visible_end:
        for i in range(left_visible_start, left_visible_end + 1):
            strip.setPixelColor(i, left_color)

    if right_visible_start <= right_visible_end:
        for i in range(right_visible_start, right_visible_end + 1):
            strip.setPixelColor(i, right_color)

    strip.show()


def flash_all(color, times=4, delay=0.15):
    for _ in range(times):
        for i in range(GAME_LEDS):
            strip.setPixelColor(i, color)
        strip.show()
        time.sleep(delay)

        for i in range(GAME_LEDS):
            strip.setPixelColor(i, OFF)
        strip.show()
        time.sleep(delay)


def flash_side(side, color, times=6, delay=0.15):
    for _ in range(times):
        for i in range(TOTAL_LEDS):
            strip.setPixelColor(i, OFF)

        if side == "left":
            set_half(LEFT_START, LEFT_END, color)
        else:
            set_half(RIGHT_START, RIGHT_END, color)

        strip.show()
        time.sleep(delay)

        for i in range(TOTAL_LEDS):
            strip.setPixelColor(i, OFF)

        strip.show()
        time.sleep(delay)


def countdown_intro():
    clear_all()

    for count in range(3, 0, -1):
        clear_all()

        start = (GAME_LEDS - count) // 2
        for i in range(count):
            strip.setPixelColor(start + i, YELLOW)

        strip.show()
        time.sleep(0.7)

    flash_all(WHITE, times=2, delay=0.12)


def wait_for_release():
    while left_button.is_pressed or right_button.is_pressed:
        time.sleep(0.01)


def swap_hot_to_other_side():
    global hot_side

    if hot_side == "left":
        hot_side = "right"
        print("Hot potato moved to RIGHT side.")
    else:
        hot_side = "left"
        print("Hot potato moved to LEFT side.")

    show_sides()


def play_game():
    global hot_side

    hot_side = random.choice(["left", "right"])

    print("Hot Potato Game")
    print("Red = Hot colour")
    print("Green = Safe colour")
    print("Timer = 30 seconds")
    print("Whoever has red when time runs out loses.")
    print("Press Ctrl + C to stop.")
    print()

    countdown_intro()
    show_sides()

    print(f"Starting hot side: {hot_side.upper()}")

    wait_for_release()

    start_time = time.monotonic()

    left_was_pressed = left_button.is_pressed
    right_was_pressed = right_button.is_pressed

    while True:
        now = time.monotonic()
        elapsed = now - start_time

        if elapsed >= GAME_TIME:
            break

        left_now = left_button.is_pressed
        right_now = right_button.is_pressed

        left_edge = left_now and not left_was_pressed
        right_edge = right_now and not right_was_pressed

        if hot_side == "left" and left_edge:
            swap_hot_to_other_side()

        elif hot_side == "right" and right_edge:
            swap_hot_to_other_side()

        left_was_pressed = left_now
        right_was_pressed = right_now

        show_timer_progress(elapsed)

        time.sleep(POLL_INTERVAL)

    print()
    print("Time is up!")

    if hot_side == "left":
        print("LEFT PLAYER LOSES.")
        print("RIGHT PLAYER WINS.")
        flash_side("left", HOT_COLOR)
        flash_side("right", SAFE_COLOR, times=3)
    else:
        print("RIGHT PLAYER LOSES.")
        print("LEFT PLAYER WINS.")
        flash_side("right", HOT_COLOR)
        flash_side("left", SAFE_COLOR, times=3)

    clear_all()


try:
    play_game()

except KeyboardInterrupt:
    clear_all()
    print()
    print("Game stopped.")