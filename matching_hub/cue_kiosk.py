import math
import os
import socket
import time
from dataclasses import dataclass
from pathlib import Path

from cue_games import play_game
from cue_screen_games import play_screen_game
from led_client import LedClient
from nfc_readers import DualPn532Readers, debounce_uid


WIDTH = int(os.environ.get("CUE_KIOSK_WIDTH", "640"))
HEIGHT = int(os.environ.get("CUE_KIOSK_HEIGHT", "480"))
FPS = 30
FULLSCREEN = os.environ.get("CUE_KIOSK_FULLSCREEN", "1") != "0"
TRUE_FULLSCREEN = os.environ.get("CUE_KIOSK_TRUE_FULLSCREEN", "0") == "1"
DISPLAY_INDEX = int(os.environ.get("CUE_KIOSK_DISPLAY_INDEX", "0"))
NFC_ENABLED = os.environ.get("CUE_KIOSK_NFC_ENABLED", "0") == "1"

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
SERVICE_ACCOUNT_PATH = Path(
    os.environ.get("CUE_FIREBASE_SERVICE_ACCOUNT", ROOT / "serviceAccountKey.json")
)
RIGHT_PN532_CS = os.environ.get("CUE_RIGHT_PN532_CS", "D8")
MATCHING_RESET_SOCKET = os.environ.get(
    "CUE_MATCHING_RESET_SOCKET",
    "/tmp/cue-matching-hub.sock",
)

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
    rules_image: str


GAMES = [
    Game("Tug of War", "game_tug_of_war.png", "tug_of_war", "rules_tug_of_war.png"),
    Game("Hot Potato", "game_hot_potato.png", "hot_potato", "rules_hot_potato.png"),
    Game("Reaction Time", "game_reaction_time.png", "reaction_time", "rules_reaction_time.png"),
    Game(
        "5 Second Reaction",
        "game_five_second_reaction.png",
        "five_second_reaction",
        "rules_five_second_reaction.png",
    ),
    Game("Darts", "game_darts.png", "darts", "rules_darts.png"),
    Game("Truth or Dare", "game_truth_or_dare.png", "truth_or_dare", "rules_truth_or_dare.png"),
    Game("Exit", "game_exit.png", "exit", "game_exit.png"),
]

SCREEN_GAMES = {"five_second_reaction", "darts", "truth_or_dare"}

IMAGE_CACHE = {}


class FirebaseProfiles:
    def __init__(self, service_account_path):
        self.service_account_path = Path(service_account_path)
        self.db = None

    def initialise(self):
        if self.db is not None:
            return

        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            cred = credentials.Certificate(str(self.service_account_path))
            firebase_admin.initialize_app(cred)

        self.db = firestore.client()
        print("Firebase profile verifier ready.")

    def delete_profile_records(self, nfc_uids):
        self.initialise()

        for nfc_uid in nfc_uids:
            print(f"Clearing Firebase records for NFC UID: {nfc_uid}")
            self.db.collection("profiles").document(nfc_uid).delete()
            self.db.collection("wristbands").document(nfc_uid).delete()


class NfcScanners:
    def __init__(self):
        self.available = False
        self.readers = None
        self.last_left = (None, 0.0)
        self.last_right = (None, 0.0)

        try:
            self.readers = DualPn532Readers(spi_cs=RIGHT_PN532_CS)
            self.readers.initialise()
            self.available = True
        except Exception as error:
            print(f"PN532 readers unavailable: {error}")

    def scan(self):
        if not self.available:
            return None, None

        seen = self.readers.read_once(timeout=0.05)
        left_uid = seen["left"]
        right_uid = seen["right"]

        self.last_left, left_new = debounce_uid(self.last_left, left_uid)
        self.last_right, right_new = debounce_uid(self.last_right, right_uid)

        return (
            left_uid if left_new else None,
            right_uid if right_new else None,
        )

    def reset(self):
        self.last_left = (None, 0.0)
        self.last_right = (None, 0.0)


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


def draw_waiting(surface, left_ready, right_ready, message=None):
    draw_clock(surface)
    label = "Scan both wristbands"
    if left_ready and not right_ready:
        label = "Left wristband scanned"
    elif right_ready and not left_ready:
        label = "Right wristband scanned"
    elif left_ready and right_ready:
        label = "Checking match"
    draw_centered_text(surface, label, 28, SOFT_PINK, (WIDTH // 2, HEIGHT - 58))

    if message:
        draw_centered_text(surface, message, 20, SOFT_PINK, (WIDTH // 2, HEIGHT - 28))


def draw_game_card(surface, game):
    image = load_image(game.image, (WIDTH, HEIGHT))
    if image:
        surface.blit(image, (0, 0))
        return

    surface.fill(BG_LIGHT)
    draw_centered_text(surface, game.title, 42, BLACK, (WIDTH // 2, HEIGHT // 2))


def draw_rules_page(surface, game):
    image = load_image(game.rules_image, (WIDTH, HEIGHT))
    if image:
        surface.blit(image, (0, 0))
        return

    surface.fill(BG_DARK)
    draw_centered_text(surface, game.title, 38, WHITE, (WIDTH // 2, HEIGHT // 2 - 20))
    draw_centered_text(
        surface,
        "Press both buttons to start",
        24,
        SOFT_PINK,
        (WIDTH // 2, HEIGHT // 2 + 42),
    )


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


def wait_for_both_buttons(screen, buttons, game):
    left_was_pressed = False
    right_was_pressed = False

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise KeyboardInterrupt
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                raise KeyboardInterrupt

        keys = pygame.key.get_pressed()
        left_pressed, right_pressed = buttons.states(keys)

        draw_rules_page(screen, game)
        pygame.display.flip()

        if (
            left_pressed
            and right_pressed
            and not (left_was_pressed and right_was_pressed)
        ):
            while True:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        raise KeyboardInterrupt
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        raise KeyboardInterrupt

                keys = pygame.key.get_pressed()
                release_left, release_right = buttons.states(keys)
                if not release_left and not release_right:
                    return
                time.sleep(0.01)

        left_was_pressed = left_pressed
        right_was_pressed = right_pressed
        time.sleep(0.02)


def launch_game(game, screen, buttons, strip):
    strip.clear()
    draw_rules_page(screen, game)
    pygame.display.flip()
    wait_for_both_buttons(screen, buttons, game)
    draw_rules_page(screen, game)
    pygame.display.flip()

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


def reset_matching_hub():
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(1.0)
            connection.connect(MATCHING_RESET_SOCKET)
            connection.sendall(b"RESET\n")
            response = connection.recv(64).decode(errors="replace").strip()
            print(f"Matching hub reset response: {response}")
    except OSError as error:
        print(f"Could not reset matching hub: {error}")


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
    nfc_scanners = NfcScanners() if NFC_ENABLED else None
    firebase_profiles = FirebaseProfiles(SERVICE_ACCOUNT_PATH)

    state = "clock"
    left_ready = True
    right_ready = True
    left_nfc_uid = None
    right_nfc_uid = None
    session_nfc_uids = []
    kiosk_status = None
    selected_game = 0
    previous_left = False
    previous_right = False
    game_started = False

    state = "menu"

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
            if nfc_scanners is not None:
                left_scan_uid, right_scan_uid = nfc_scanners.scan()
            else:
                left_scan_uid, right_scan_uid = None, None

            if state == "clock":
                if left_scan_uid:
                    left_ready = True
                    left_nfc_uid = left_scan_uid
                    kiosk_status = f"Left: {left_nfc_uid[-6:]}"
                    print(f"LEFT NFC scanned: {left_nfc_uid}")
                    state = "waiting"
                if right_scan_uid:
                    right_ready = True
                    right_nfc_uid = right_scan_uid
                    kiosk_status = f"Right: {right_nfc_uid[-6:]}"
                    print(f"RIGHT NFC scanned: {right_nfc_uid}")
                    state = "waiting"
                draw_waiting(screen, left_ready, right_ready, kiosk_status)
                led_ready(strip, now, left_ready, right_ready)

            elif state == "waiting":
                if left_scan_uid:
                    left_ready = True
                    left_nfc_uid = left_scan_uid
                    kiosk_status = f"Left: {left_nfc_uid[-6:]}"
                    print(f"LEFT NFC scanned: {left_nfc_uid}")
                if right_scan_uid:
                    right_ready = True
                    right_nfc_uid = right_scan_uid
                    kiosk_status = f"Right: {right_nfc_uid[-6:]}"
                    print(f"RIGHT NFC scanned: {right_nfc_uid}")

                draw_waiting(screen, left_ready, right_ready, kiosk_status)
                led_ready(strip, now, left_ready, right_ready)

                if left_ready and right_ready:
                    pygame.display.flip()

                    if left_nfc_uid != right_nfc_uid:
                        session_nfc_uids = [left_nfc_uid, right_nfc_uid]
                        state = "menu"
                    else:
                        kiosk_status = "Scan two different wristbands"
                        draw_waiting(screen, False, False, kiosk_status)
                        pygame.display.flip()
                        time.sleep(1.5)
                        state = "clock"

                    left_ready = False
                    right_ready = False
                    left_nfc_uid = None
                    right_nfc_uid = None
                    kiosk_status = None
                    if nfc_scanners is not None:
                        nfc_scanners.reset()
                    selected_game = 0
                    state = "clock"

            elif state == "menu":
                if left_edge:
                    selected_game = (selected_game + 1) % len(GAMES)

                draw_game_card(screen, GAMES[selected_game])

                led_ready(strip, now, True, True)

                if right_edge and not game_started:
                    selected = GAMES[selected_game]

                    if selected.script == "exit":
                        if session_nfc_uids:
                            try:
                                firebase_profiles.delete_profile_records(session_nfc_uids)
                            except Exception as error:
                                print(f"Could not clear Firebase profiles: {error}")
                            reset_matching_hub()
                            session_nfc_uids = []
                        state = "menu"
                        left_ready = True
                        right_ready = True
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
