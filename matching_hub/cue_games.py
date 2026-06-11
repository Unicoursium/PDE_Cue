import argparse
import random
import time

from gpiozero import Button

from led_client import Color, PixelStrip


LED_COUNT = 40
HALF_LED_COUNT = LED_COUNT // 2
TUG_STEP_SIZE = 2
LEFT_BUTTON_PIN = 23
RIGHT_BUTTON_PIN = 24

OFF = Color(0, 0, 0)
WHITE = Color(255, 255, 255)
LEFT_COLOR = Color(255, 0, 255)
RIGHT_COLOR = Color(0, 255, 255)
RED = Color(255, 0, 0)
GREEN = Color(0, 255, 0)
YELLOW = Color(255, 180, 0)


class GameHardware:
    def __init__(self, bounce_time=0.03, left_button=None, right_button=None):
        self.strip = PixelStrip(LED_COUNT)
        self.strip.begin()
        self.owns_buttons = left_button is None or right_button is None

        if self.owns_buttons:
            self.left_button = Button(
                LEFT_BUTTON_PIN,
                pull_up=True,
                bounce_time=bounce_time,
            )
            self.right_button = Button(
                RIGHT_BUTTON_PIN,
                pull_up=True,
                bounce_time=bounce_time,
            )
        else:
            self.left_button = left_button
            self.right_button = right_button

    def clear(self):
        self.fill(OFF)

    def fill(self, color):
        for index in range(LED_COUNT):
            self.strip.setPixelColor(index, color)
        self.strip.show()

    def set_pixels(self, pixels):
        for index in range(LED_COUNT):
            self.strip.setPixelColor(index, pixels.get(index, OFF))
        self.strip.show()

    def wait_for_release(self):
        while self.left_button.is_pressed or self.right_button.is_pressed:
            time.sleep(0.01)

    def flash(self, color, times=5, delay=0.15):
        for _ in range(times):
            self.fill(color)
            time.sleep(delay)
            self.clear()
            time.sleep(delay)

    def close(self):
        self.clear()
        if self.owns_buttons:
            self.left_button.close()
            self.right_button.close()


class TugOfWar:
    def __init__(self, left_button=None, right_button=None):
        self.hardware = GameHardware(
            left_button=left_button,
            right_button=right_button,
        )

    def show_position(self, position):
        pixels = {}
        for index in range(LED_COUNT):
            if index < position:
                pixels[index] = LEFT_COLOR
            elif index > position:
                pixels[index] = RIGHT_COLOR
            else:
                pixels[index] = WHITE
        self.hardware.set_pixels(pixels)

    def countdown(self):
        self.hardware.wait_for_release()
        for count in range(3, 0, -1):
            pixels = {}
            start = (LED_COUNT - count) // 2
            for offset in range(count):
                pixels[start + offset] = YELLOW
            self.hardware.set_pixels(pixels)
            time.sleep(0.7)
        self.hardware.fill(GREEN)
        time.sleep(0.4)
        self.hardware.wait_for_release()

    def play(self):
        left_score = 0
        right_score = 0
        round_number = 1

        print("Tug of War: first to 3 points wins.")

        while left_score < 3 and right_score < 3 and round_number <= 5:
            print(f"Round {round_number}: Left {left_score} - Right {right_score}")
            self.countdown()
            position = LED_COUNT // 2
            self.show_position(position)
            left_was_pressed = False
            right_was_pressed = False

            while 0 < position < LED_COUNT - 1:
                left_now = self.hardware.left_button.is_pressed
                right_now = self.hardware.right_button.is_pressed
                left_edge = left_now and not left_was_pressed
                right_edge = right_now and not right_was_pressed

                if left_edge and not right_edge:
                    position = min(LED_COUNT - 1, position + TUG_STEP_SIZE)
                    self.show_position(position)
                elif right_edge and not left_edge:
                    position = max(0, position - TUG_STEP_SIZE)
                    self.show_position(position)

                left_was_pressed = left_now
                right_was_pressed = right_now
                time.sleep(0.005)

            if position >= LED_COUNT - 1:
                left_score += 1
                print("Left wins the round.")
                self.hardware.flash(LEFT_COLOR, times=4)
            else:
                right_score += 1
                print("Right wins the round.")
                self.hardware.flash(RIGHT_COLOR, times=4)

            round_number += 1

        winner_color = LEFT_COLOR if left_score > right_score else RIGHT_COLOR
        print(f"Tug of War final score: Left {left_score} - Right {right_score}")
        self.hardware.flash(winner_color, times=8)


def play_hot_potato(hardware):
    hot_side = random.choice(("left", "right"))
    game_time = 8.0

    def show_progress(elapsed):
        progress = max(0.0, min(1.0, elapsed / game_time))
        off_per_side = int((HALF_LED_COUNT - 1) * progress)
        pixels = {}
        left_color = RED if hot_side == "left" else GREEN
        right_color = GREEN if hot_side == "left" else RED

        for index in range(0, HALF_LED_COUNT - off_per_side):
            pixels[index] = left_color
        for index in range(HALF_LED_COUNT + off_per_side, LED_COUNT):
            pixels[index] = right_color
        hardware.set_pixels(pixels)

    print(f"Hot Potato, starting side: {hot_side.upper()}")
    for count in range(3, 0, -1):
        pixels = {}
        start = (LED_COUNT - count) // 2
        for offset in range(count):
            pixels[start + offset] = YELLOW
        hardware.set_pixels(pixels)
        time.sleep(0.7)

    hardware.wait_for_release()
    start_time = time.monotonic()
    left_was_pressed = False
    right_was_pressed = False

    while True:
        elapsed = time.monotonic() - start_time
        if elapsed >= game_time:
            break

        left_now = hardware.left_button.is_pressed
        right_now = hardware.right_button.is_pressed
        if hot_side == "left" and left_now and not left_was_pressed:
            hot_side = "right"
            print("Hot potato moved to RIGHT.")
        elif hot_side == "right" and right_now and not right_was_pressed:
            hot_side = "left"
            print("Hot potato moved to LEFT.")

        left_was_pressed = left_now
        right_was_pressed = right_now
        show_progress(elapsed)
        time.sleep(0.01)

    losing_range = (
        range(0, HALF_LED_COUNT)
        if hot_side == "left"
        else range(HALF_LED_COUNT, LED_COUNT)
    )
    winning_range = (
        range(HALF_LED_COUNT, LED_COUNT)
        if hot_side == "left"
        else range(0, HALF_LED_COUNT)
    )
    print(f"{hot_side.upper()} PLAYER LOSES.")

    for _ in range(6):
        hardware.set_pixels({index: RED for index in losing_range})
        time.sleep(0.15)
        hardware.clear()
        time.sleep(0.15)
    hardware.set_pixels({index: GREEN for index in winning_range})
    time.sleep(1.2)


def play_reaction_time(hardware):
    left_score = 0
    right_score = 0
    round_number = 1

    def show_score():
        pixels = {}
        for index in range(left_score):
            pixels[index] = LEFT_COLOR
        for index in range(right_score):
            pixels[LED_COUNT - 1 - index] = RIGHT_COLOR
        hardware.set_pixels(pixels)
        time.sleep(1.2)

    print("Reaction Time: first to 3 points wins.")
    while left_score < 3 and right_score < 3 and round_number <= 5:
        print(f"Round {round_number}: Left {left_score} - Right {right_score}")
        hardware.flash(WHITE, times=2, delay=0.12)
        hardware.wait_for_release()
        hardware.fill(RED)

        wait_until = time.monotonic() + random.uniform(0.5, 3.0)
        left_was_pressed = False
        right_was_pressed = False
        winner = None

        while time.monotonic() < wait_until:
            left_now = hardware.left_button.is_pressed
            right_now = hardware.right_button.is_pressed
            if left_now and not left_was_pressed:
                winner = "right"
                print("Left pressed too early.")
                break
            if right_now and not right_was_pressed:
                winner = "left"
                print("Right pressed too early.")
                break
            left_was_pressed = left_now
            right_was_pressed = right_now
            time.sleep(0.001)

        if winner is None:
            hardware.fill(GREEN)
            green_time = time.monotonic()
            left_was_pressed = hardware.left_button.is_pressed
            right_was_pressed = hardware.right_button.is_pressed

            while winner is None:
                now = time.monotonic()
                left_now = hardware.left_button.is_pressed
                right_now = hardware.right_button.is_pressed
                left_edge = left_now and not left_was_pressed
                right_edge = right_now and not right_was_pressed
                if left_edge and right_edge:
                    print("Tie, replaying round.")
                    hardware.flash(WHITE)
                    break
                if left_edge:
                    winner = "left"
                    print(f"Left reaction: {now - green_time:.3f}s")
                elif right_edge:
                    winner = "right"
                    print(f"Right reaction: {now - green_time:.3f}s")
                left_was_pressed = left_now
                right_was_pressed = right_now
                time.sleep(0.001)

        if winner == "left":
            left_score += 1
            round_number += 1
            hardware.flash(LEFT_COLOR)
        elif winner == "right":
            right_score += 1
            round_number += 1
            hardware.flash(RIGHT_COLOR)

        hardware.wait_for_release()
        show_score()

    hardware.flash(LEFT_COLOR if left_score > right_score else RIGHT_COLOR, times=8)


def play_game(game_name, left_button=None, right_button=None):
    if game_name == "tug_of_war":
        game = TugOfWar(left_button=left_button, right_button=right_button)
        try:
            game.play()
        finally:
            game.hardware.close()
        return

    hardware = GameHardware(
        left_button=left_button,
        right_button=right_button,
    )
    try:
        if game_name == "hot_potato":
            play_hot_potato(hardware)
        else:
            play_reaction_time(hardware)
    finally:
        hardware.close()


def main():
    parser = argparse.ArgumentParser(description="Cue LED games")
    parser.add_argument(
        "game",
        choices=("tug_of_war", "hot_potato", "reaction_time"),
    )
    args = parser.parse_args()
    play_game(args.game)


if __name__ == "__main__":
    main()
