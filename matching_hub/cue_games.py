import argparse
import random
import time

from gpiozero import Button

from led_layout import (
    LED_COUNT,
    TUG_OF_WAR_CENTER_POSITION,
    TUG_OF_WAR_PATH,
    score_leds,
    side_leds,
)
from led_client import Color, PixelStrip


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
    def __init__(self, left_button=None, right_button=None, points_to_win=3):
        self.hardware = GameHardware(
            left_button=left_button,
            right_button=right_button,
        )
        self.points_to_win = points_to_win

    def show_position(self, position):
        pixels = {}
        for path_position, led_index in enumerate(TUG_OF_WAR_PATH):
            if path_position < position:
                pixels[led_index] = LEFT_COLOR
            elif path_position > position:
                pixels[led_index] = RIGHT_COLOR
            else:
                pixels[led_index] = WHITE
        self.hardware.set_pixels(pixels)

    def countdown(self):
        self.hardware.wait_for_release()
        for count in range(3, 0, -1):
            pixels = {}
            start = TUG_OF_WAR_CENTER_POSITION - count // 2
            for offset in range(count):
                path_position = start + offset
                if 0 <= path_position < len(TUG_OF_WAR_PATH):
                    pixels[TUG_OF_WAR_PATH[path_position]] = YELLOW
            self.hardware.set_pixels(pixels)
            time.sleep(0.7)
        self.hardware.fill(GREEN)
        time.sleep(0.4)
        self.hardware.wait_for_release()

    def play(self):
        left_score = 0
        right_score = 0
        round_number = 1

        max_rounds = self.points_to_win * 2 - 1
        print(f"Tug of War: first to {self.points_to_win} point(s) wins.")

        while (
            left_score < self.points_to_win
            and right_score < self.points_to_win
            and round_number <= max_rounds
        ):
            print(f"Round {round_number}: Left {left_score} - Right {right_score}")
            self.countdown()
            position = TUG_OF_WAR_CENTER_POSITION
            self.show_position(position)
            left_was_pressed = False
            right_was_pressed = False

            while 0 < position < len(TUG_OF_WAR_PATH) - 1:
                left_now = self.hardware.left_button.is_pressed
                right_now = self.hardware.right_button.is_pressed
                left_edge = left_now and not left_was_pressed
                right_edge = right_now and not right_was_pressed

                if left_edge and not right_edge:
                    position = min(len(TUG_OF_WAR_PATH) - 1, position + TUG_STEP_SIZE)
                    self.show_position(position)
                elif right_edge and not left_edge:
                    position = max(0, position - TUG_STEP_SIZE)
                    self.show_position(position)

                left_was_pressed = left_now
                right_was_pressed = right_now
                time.sleep(0.005)

            if position >= len(TUG_OF_WAR_PATH) - 1:
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


def play_hot_potato(hardware, game_time=8.0):
    hot_side = random.choice(("left", "right"))

    def show_progress(elapsed):
        progress = max(0.0, min(1.0, elapsed / game_time))
        left_visible = max(0, len(side_leds("left")) - int(len(side_leds("left")) * progress))
        right_visible = max(0, len(side_leds("right")) - int(len(side_leds("right")) * progress))
        pixels = {}
        left_color = RED if hot_side == "left" else GREEN
        right_color = GREEN if hot_side == "left" else RED

        for index in score_leds("left", left_visible):
            pixels[index] = left_color
        for index in score_leds("right", right_visible):
            pixels[index] = right_color
        hardware.set_pixels(pixels)

    print(f"Hot Potato, starting side: {hot_side.upper()}")
    for count in range(3, 0, -1):
        pixels = {}
        start = TUG_OF_WAR_CENTER_POSITION - count // 2
        for offset in range(count):
            path_position = start + offset
            if 0 <= path_position < len(TUG_OF_WAR_PATH):
                pixels[TUG_OF_WAR_PATH[path_position]] = YELLOW
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

    losing_range = side_leds(hot_side)
    winning_range = side_leds("right" if hot_side == "left" else "left")
    print(f"{hot_side.upper()} PLAYER LOSES.")

    for _ in range(6):
        hardware.set_pixels({index: RED for index in losing_range})
        time.sleep(0.15)
        hardware.clear()
        time.sleep(0.15)
    hardware.set_pixels({index: GREEN for index in winning_range})
    time.sleep(1.2)


def play_reaction_time(hardware, points_to_win=3):
    left_score = 0
    right_score = 0
    round_number = 1

    def show_score():
        pixels = {}
        for index in score_leds("left", left_score):
            pixels[index] = LEFT_COLOR
        for index in score_leds("right", right_score):
            pixels[index] = RIGHT_COLOR
        hardware.set_pixels(pixels)
        time.sleep(1.2)

    max_rounds = points_to_win * 2 - 1
    print(f"Reaction Time: first to {points_to_win} point(s) wins.")
    while left_score < points_to_win and right_score < points_to_win and round_number <= max_rounds:
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


def play_game(
    game_name,
    left_button=None,
    right_button=None,
    points_to_win=None,
    hot_potato_seconds=None,
):
    if game_name == "tug_of_war":
        game = TugOfWar(
            left_button=left_button,
            right_button=right_button,
            points_to_win=points_to_win or 3,
        )
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
            play_hot_potato(hardware, game_time=hot_potato_seconds or 8.0)
        else:
            play_reaction_time(hardware, points_to_win=points_to_win or 3)
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
