from rpi_ws281x import PixelStrip, Color
from gpiozero import Button
from signal import pause
import time
import threading

TOTAL_LEDS = 120
GAME_LEDS = 20

LED_PIN = 18
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 60
LED_INVERT = False
LED_CHANNEL = 0

P1_BUTTON_PIN = 23
P2_BUTTON_PIN = 24

P1_COLOR = Color(0, 255, 255)
P2_COLOR = Color(255, 0, 255)
CENTER_COLOR = Color(255, 255, 255)
COUNTDOWN_COLOR = Color(255, 180, 0)
READY_COLOR = Color(0, 255, 80)
OFF = Color(0, 0, 0)

START_POSITION = GAME_LEDS // 2
WIN_LEFT = 0
WIN_RIGHT = GAME_LEDS - 1

RESET_HOLD_TIME = 3.0
RESET_CHECK_INTERVAL = 0.02

position = START_POSITION
game_over = False
reset_triggered = False
is_resetting = False

lock = threading.RLock()

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

p1_button = Button(P1_BUTTON_PIN, pull_up=True, bounce_time=0.03)
p2_button = Button(P2_BUTTON_PIN, pull_up=True, bounce_time=0.03)


def clear_all():
    for i in range(TOTAL_LEDS):
        strip.setPixelColor(i, OFF)
    strip.show()


def show_position():
    clear_all()

    for i in range(GAME_LEDS):
        if i < position:
            strip.setPixelColor(i, P2_COLOR)
        elif i > position:
            strip.setPixelColor(i, P1_COLOR)

    strip.setPixelColor(position, CENTER_COLOR)
    strip.show()


def flash_winner(color):
    for _ in range(6):
        for i in range(GAME_LEDS):
            strip.setPixelColor(i, color)
        strip.show()
        time.sleep(0.18)

        for i in range(GAME_LEDS):
            strip.setPixelColor(i, OFF)
        strip.show()
        time.sleep(0.18)


def flash_reset():
    for _ in range(3):
        for i in range(GAME_LEDS):
            strip.setPixelColor(i, CENTER_COLOR)
        strip.show()
        time.sleep(0.12)

        for i in range(GAME_LEDS):
            strip.setPixelColor(i, OFF)
        strip.show()
        time.sleep(0.12)


def countdown():
    clear_all()

    for count in range(3, 0, -1):
        clear_all()
        start = (GAME_LEDS - count) // 2
        for i in range(count):
            strip.setPixelColor(start + i, COUNTDOWN_COLOR)
        strip.show()
        time.sleep(0.7)

    clear_all()
    for i in range(GAME_LEDS):
        strip.setPixelColor(i, READY_COLOR)
    strip.show()
    time.sleep(0.4)

    show_position()


def reset_game():
    global position, game_over, is_resetting

    with lock:
        if is_resetting:
            return

        is_resetting = True
        position = START_POSITION
        game_over = False

    flash_reset()
    countdown()

    with lock:
        is_resetting = False


def player1_press():
    global position, game_over

    with lock:
        if game_over or is_resetting:
            return

        if p1_button.is_pressed and p2_button.is_pressed:
            return

        position += 1

        if position >= WIN_RIGHT:
            position = WIN_RIGHT
            game_over = True
            show_position()
            flash_winner(P2_COLOR)
            time.sleep(1)
            reset_game()
            return

        show_position()


def player2_press():
    global position, game_over

    with lock:
        if game_over or is_resetting:
            return

        if p1_button.is_pressed and p2_button.is_pressed:
            return

        position -= 1

        if position <= WIN_LEFT:
            position = WIN_LEFT
            game_over = True
            show_position()
            flash_winner(P1_COLOR)
            time.sleep(1)
            reset_game()
            return

        show_position()


def dual_button_reset_loop():
    global reset_triggered

    hold_start = None

    while True:
        both_pressed = p1_button.is_pressed and p2_button.is_pressed

        if both_pressed:
            if hold_start is None:
                hold_start = time.monotonic()

            elapsed = time.monotonic() - hold_start

            if elapsed >= RESET_HOLD_TIME and not reset_triggered:
                reset_triggered = True
                reset_game()

        else:
            hold_start = None
            reset_triggered = False

        time.sleep(RESET_CHECK_INTERVAL)


p1_button.when_pressed = player1_press
p2_button.when_pressed = player2_press

reset_thread = threading.Thread(target=dual_button_reset_loop, daemon=True)
reset_thread.start()

try:
    reset_game()
    pause()

except KeyboardInterrupt:
    clear_all()