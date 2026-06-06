import math
import os
import time
from dataclasses import dataclass
from pathlib import Path

from cue_games import play_game
from cue_screen_games import play_screen_game
from led_client import LedClient


WIDTH = int(os.environ.get("CUE_KIOSK_WIDTH", "640"))
HEIGHT = int(os.environ.get("CUE_KIOSK_HEIGHT", "480"))
FPS = 30
FULLSCREEN = os.environ.get("CUE_KIOSK_FULLSCREEN", "1") != "0"
TRUE_FULLSCREEN = os.environ.get("CUE_KIOSK_TRUE_FULLSCREEN", "0") == "1"
DISPLAY_INDEX = int(os.environ.get("CUE_KIOSK_DISPLAY_INDEX", "0"))

LEFT_BUTTON_PIN = int(os.environ.get("CUE_LEFT_BUTTON_PIN", "23"))
RIGHT_BUTTON_PIN = int(os.environ.get("CUE_RIGHT_BUTTON_PIN", "24"))

LED_COUNT = int(os.environ.get("CUE_KIOSK_LEDS", "40"))
HALF_LED_COUNT = LED_COUNT // 2
LEFT_LED_RANGE = range(0, HALF_LED_COUNT)
RIGHT_LED_RANGE = range(HALF_LED_COUNT, LED_COUNT)
LED_PIN = int(os.environ.get("CUE_LED_PIN", "18"))
LED_BRIGHTNESS = int(os.environ.get("CUE_LED_BRIGHTNESS", "60"))

ROOT = Path(__file__).resolve().parent
ASSET_DIR = ROOT / "assets"

BG_DARK = (34, 34, 34)
BG_LIGHT = (222, 222, 222)
BLACK = (16, 16, 18)
WHITE = (255, 255, 255)
PINK = (191, 49, 112)
SOFT_PINK = (255, 188, 216)
CYBER_YELLOW = (255, 225, 0)
PALE_PURPLE = (205, 180, 255)
@dataclass
class Game:
    title: str
    image: str
    script: str


GAMES = [
    Game("Tug of War", "game_tug_of_war.png", "tug_of_war"),
    Game("Hot Potato", "game_hot_potato.png", "hot_potato"),
    Game("Reaction Time", "game_reaction_time.png", "reaction_time"),
    Game(
        "5 Second Reaction",
        "game_five_second_reaction.png",
        "five_second_reaction",
    ),
    Game("Darts", "game_darts.png", "darts"),
    Game("Truth or Dare", "game_truth_or_dare.png", "truth_or_dare"),
    Game("Exit", "game_exit.png", "exit"),
]

SCREEN_GAMES = {"five_second_reaction", "darts", "truth_or_dare"}

IMAGE_CACHE = {}


class LedStrip:
    def __init__(self):
        self.available = False
        self.last_pixels = None
        self.last_update = 0.0

        try:
            self.client = LedClient()
            self.client.ping()
            self.available = True
            print("LED service ready.")
        except Exception as error:
            print(f"LED service unavailable: {error}")

    def set_pixels(self, pixels):
        if not self.available:
            return

        now = time.monotonic()
        if pixels == self.last_pixels or now - self.last_update < 0.05:
            return

        try:
            self.client.set_pixels(pixels)
            self.last_pixels = pixels.copy()
            self.last_update = now
        except Exception as error:
            self.available = False
            print(f"LED service connection lost: {error}")

    def clear(self):
        if not self.available:
            return

        try:
            self.client.clear()
        except Exception as error:
            print(f"Could not clear LED strip: {error}")


class Buttons:
    def __init__(self):
        self.left = None
        self.right = None

        try:
            from gpiozero import Button

            self.left = Button(LEFT_BUTTON_PIN, pull_up=True, bounce_time=0.04)
            self.right = Button(RIGHT_BUTTON_PIN, pull_up=True, bounce_time=0.04)
            print("GPIO buttons ready.")
        except Exception as error:
            print(f"GPIO buttons disabled, keyboard fallback active: {error}")

    def states(self, keys):
        left_keyboard = keys[pygame.K_LEFT] or keys[pygame.K_a] or keys[pygame.K_1]
        right_keyboard = keys[pygame.K_RIGHT] or keys[pygame.K_d] or keys[pygame.K_2]
        both_keyboard = keys[pygame.K_SPACE] or keys[pygame.K_RETURN]

        left_pressed = left_keyboard or both_keyboard
        right_pressed = right_keyboard or both_keyboard

        if self.left is not None:
            left_pressed = left_pressed or self.left.is_pressed
        if self.right is not None:
            right_pressed = right_pressed or self.right.is_pressed

        return left_pressed, right_pressed

    def close(self):
        for button in (self.left, self.right):
            if button is not None:
                button.close()
        self.left = None
        self.right = None


def load_image(filename, size=None):
    cache_key = (filename, size)
    if cache_key in IMAGE_CACHE:
        return IMAGE_CACHE[cache_key]

    path = ASSET_DIR / filename
    if not path.exists():
        return None

    image = pygame.image.load(str(path)).convert_alpha()
    if size is not None:
        image = pygame.transform.smoothscale(image, size)
    IMAGE_CACHE[cache_key] = image
    return image


def font(size, bold=True):
    return pygame.font.SysFont("Arial", size, bold=bold)


def clock_font(size):
    regular_font = ASSET_DIR / "clock_font_regular.ttf"
    variable_font = ASSET_DIR / "clock_font.ttf"

    if regular_font.exists():
        return pygame.font.Font(str(regular_font), size)
    if variable_font.exists():
        return pygame.font.Font(str(variable_font), size)
    return pygame.font.SysFont("Arial", size, bold=True)


def draw_centered_text(surface, text, size, color, center, bold=True):
    rendered = font(size, bold).render(text, True, color)
    rect = rendered.get_rect(center=center)
    surface.blit(rendered, rect)
    return rect


def draw_centered_text_fit(
    surface,
    text,
    max_size,
    color,
    center,
    max_width,
    bold=True,
    font_factory=None,
):
    size = max_size
    font_factory = font_factory or (lambda value: font(value, bold))

    while size > 8:
        rendered = font_factory(size).render(text, True, color)
        if rendered.get_width() <= max_width:
            break
        size -= 2

    rect = rendered.get_rect(center=center)
    surface.blit(rendered, rect)
    return rect


def draw_logo(surface, dark=False, force_white=False):
    filename = "cue_logo_light.png" if dark else "cue_logo_dark.png"
    image = load_image(filename)
    if image:
        max_width = 120
        ratio = max_width / image.get_width()
        image = pygame.transform.smoothscale(
            image,
            (max_width, max(1, int(image.get_height() * ratio))),
        )
        if force_white:
            image = pygame.mask.from_surface(image).to_surface(
                setcolor=(255, 255, 255, 255),
                unsetcolor=(0, 0, 0, 0),
            )
        surface.blit(image, image.get_rect(center=(WIDTH // 2, 50)))
        return

    draw_centered_text(surface, "cue", 48, BLACK if dark else WHITE, (WIDTH // 2, 48))
    pygame.draw.arc(
        surface,
        SOFT_PINK,
        pygame.Rect(WIDTH // 2 - 20, 58, 40, 20),
        math.radians(15),
        math.radians(165),
        4,
    )


def draw_clock(surface):
    surface.fill(BG_DARK)
    draw_logo(surface, dark=False, force_white=True)
    now = time.strftime("%H:%M")
    draw_centered_text_fit(
        surface,
        now,
        132,
        WHITE,
        (WIDTH // 2, HEIGHT // 2 + 25),
        WIDTH - 64,
        font_factory=clock_font,
    )


def draw_waiting(surface, left_ready, right_ready):
    draw_clock(surface)
    label = "Waiting for players"
    if left_ready and not right_ready:
        label = "Player 1 ready"
    elif right_ready and not left_ready:
        label = "Player 2 ready"
    draw_centered_text(surface, label, 28, SOFT_PINK, (WIDTH // 2, HEIGHT - 58))


def draw_game_card(surface, game):
    image = load_image(game.image, (WIDTH, HEIGHT))
    if image:
        surface.blit(image, (0, 0))
        return

    surface.fill(BG_LIGHT)
    draw_centered_text(surface, game.title, 42, BLACK, (WIDTH // 2, HEIGHT // 2))


def blend(a, b, amount):
    return tuple(int(a[i] + (b[i] - a[i]) * amount) for i in range(3))


def led_idle(strip, tick):
    del tick
    pixels = {}

    for index in LEFT_LED_RANGE:
        pixels[index] = CYBER_YELLOW
    for index in RIGHT_LED_RANGE:
        pixels[index] = PALE_PURPLE

    strip.set_pixels(pixels)


def led_ready(strip, tick, left_ready, right_ready):
    pixels = {}
    bounce = (math.sin(tick * 12.0) + 1) / 2
    ready_color = blend(PINK, WHITE, bounce * 0.28)

    for index in LEFT_LED_RANGE:
        pixels[index] = ready_color if left_ready else CYBER_YELLOW
    for index in RIGHT_LED_RANGE:
        pixels[index] = ready_color if right_ready else PALE_PURPLE

    strip.set_pixels(pixels)


def release_hardware(buttons, strip):
    strip.clear()
    buttons.close()


def launch_game(game, screen, buttons, strip):
    strip.clear()
    screen.fill(BG_DARK)
    draw_logo(screen, dark=False)
    draw_centered_text(screen, f"Starting {game.title}", 34, WHITE, (WIDTH // 2, HEIGHT // 2))
    pygame.display.flip()
    time.sleep(0.7)

    try:
        if game.script in SCREEN_GAMES:
            play_screen_game(
                game.script,
                screen,
                buttons.left,
                buttons.right,
                strip,
            )
        else:
            play_game(
                game.script,
                left_button=buttons.left,
                right_button=buttons.right,
            )
    finally:
        print("Game ended. Returning to Cue kiosk.")


def run():
    os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
    pygame.init()
    pygame.display.set_caption("Cue Kiosk")

    if TRUE_FULLSCREEN:
        flags = pygame.FULLSCREEN
    elif FULLSCREEN:
        flags = pygame.NOFRAME
    else:
        flags = 0

    desktop_sizes = pygame.display.get_desktop_sizes()
    if DISPLAY_INDEX >= len(desktop_sizes):
        raise ValueError(
            f"CUE_KIOSK_DISPLAY_INDEX={DISPLAY_INDEX} does not exist. "
            f"Detected displays: {desktop_sizes}"
        )

    screen = pygame.display.set_mode(
        (WIDTH, HEIGHT),
        flags,
        display=DISPLAY_INDEX,
    )
    print(
        f"Display ready: {pygame.display.get_driver()} "
        f"{screen.get_width()}x{screen.get_height()} flags={flags} "
        f"display={DISPLAY_INDEX} detected={desktop_sizes}"
    )
    clock = pygame.time.Clock()

    strip = LedStrip()
    buttons = Buttons()

    state = "clock"
    left_ready = False
    right_ready = False
    selected_game = 0
    previous_left = False
    previous_right = False
    game_started = False

    try:
        running = True
        while running:
            now = time.monotonic()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False

            keys = pygame.key.get_pressed()
            left_pressed, right_pressed = buttons.states(keys)
            left_edge = left_pressed and not previous_left
            right_edge = right_pressed and not previous_right

            if state == "clock":
                if left_edge:
                    left_ready = True
                    state = "waiting"
                if right_edge:
                    right_ready = True
                    state = "waiting"
                draw_waiting(screen, left_ready, right_ready)
                led_ready(strip, now, left_ready, right_ready)

            elif state == "waiting":
                if left_edge:
                    left_ready = True
                if right_edge:
                    right_ready = True

                draw_waiting(screen, left_ready, right_ready)
                led_ready(strip, now, left_ready, right_ready)

                if left_ready and right_ready:
                    state = "menu"

            elif state == "menu":
                if left_edge:
                    selected_game = (selected_game + 1) % len(GAMES)

                draw_game_card(screen, GAMES[selected_game])

                led_ready(strip, now, True, True)

                if right_edge and not game_started:
                    selected = GAMES[selected_game]

                    if selected.script == "exit":
                        state = "clock"
                        left_ready = False
                        right_ready = False
                        selected_game = 0
                    else:
                        game_started = True
                        pygame.display.flip()
                        launch_game(selected, screen, buttons, strip)
                        state = "menu"
                        game_started = False

            previous_left = left_pressed
            previous_right = right_pressed

            pygame.display.flip()
            clock.tick(FPS)

    finally:
        release_hardware(buttons, strip)
        pygame.quit()


if __name__ == "__main__":
    try:
        import pygame
    except ImportError:
        print("pygame is required. Install it with: pip3 install pygame --break-system-packages")
        raise

    run()
