import math
import os
import random
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from cue_games import play_game
from cue_screen_games import play_screen_game
from led_layout import LED_COUNT, LEFT_SIDE, RIGHT_SIDE
from led_client import LedClient
from nfc_readers import DualPn532Readers, debounce_uid


WIDTH = int(os.environ.get("CUE_KIOSK_WIDTH", "640"))
HEIGHT = int(os.environ.get("CUE_KIOSK_HEIGHT", "480"))
FPS = 30
FULLSCREEN = os.environ.get("CUE_KIOSK_FULLSCREEN", "1") != "0"
TRUE_FULLSCREEN = os.environ.get("CUE_KIOSK_TRUE_FULLSCREEN", "0") == "1"
DISPLAY_INDEX = int(os.environ.get("CUE_KIOSK_DISPLAY_INDEX", "0"))
NFC_ENABLED = os.environ.get("CUE_KIOSK_NFC_ENABLED", "1") == "1"

LEFT_BUTTON_PIN = int(os.environ.get("CUE_LEFT_BUTTON_PIN", "23"))
RIGHT_BUTTON_PIN = int(os.environ.get("CUE_RIGHT_BUTTON_PIN", "24"))

LEFT_LED_RANGE = LEFT_SIDE
RIGHT_LED_RANGE = RIGHT_SIDE
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
DEBUG_SCAN_HOLD_SECONDS = 3.0
TOKEN_DISPENSER_ENABLED = os.environ.get("CUE_TOKEN_DISPENSER_ENABLED", "1") == "1"
TOKEN_LEFT_SERVO_PIN = int(os.environ.get("CUE_TOKEN_LEFT_SERVO_PIN", "17"))
TOKEN_RIGHT_SERVO_PIN = int(os.environ.get("CUE_TOKEN_RIGHT_SERVO_PIN", "25"))
TOKEN_RELAY_PIN = int(os.environ.get("CUE_TOKEN_RELAY_PIN", "22"))

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


@dataclass
class AssignedGame:
    game: Game
    points_to_win: int = None
    hot_potato_seconds: float = None


@dataclass
class KioskProfile:
    document_id: str
    name: str
    nfc_uid: str
    matched_preference: str
    raw_matched_preference: str


@dataclass
class KioskMatch:
    document_id: str
    profiles: list[KioskProfile]

    def profile_for_nfc_uid(self, nfc_uid):
        for profile in self.profiles:
            if profile.nfc_uid == nfc_uid:
                return profile
        return None


def create_debug_profile(side, nfc_uid):
    return KioskProfile(
        document_id=f"debug-{side}-{nfc_uid}",
        name=f"Debug {side.title()}",
        nfc_uid=nfc_uid,
        raw_matched_preference="no help at all, I'll steer the convo",
        matched_preference="no help at all, I'll steer the convo",
    )


GAMES = [
    Game("Tug of War", "start_tug_of_war.png", "tug_of_war", "rules_tug_of_war_new.png"),
    Game("Hot Potato", "start_hot_potato.png", "hot_potato", "rules_hot_potato_new.png"),
    Game("Reaction Time", "start_reaction_time.png", "reaction_time", "rules_reaction_time_new.png"),
    Game(
        "5 Second Reaction",
        "start_five_second_reaction.png",
        "five_second_reaction",
        "rules_five_second_reaction_new.png",
    ),
    Game("Darts", "start_darts.png", "darts", "rules_darts_new.png"),
    Game("Truth or Dare", "start_truth_or_dare.png", "truth_or_dare", "rules_truth_or_dare_new.png"),
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

    def find_profile_by_nfc_uid(self, nfc_uid):
        self.initialise()

        docs = list(
            self.db
            .collection("profiles")
            .where("nfcUid", "==", nfc_uid)
            .limit(1)
            .stream()
        )

        if not docs:
            return None

        doc = docs[0]
        data = doc.to_dict() or {}
        matched_preference = str(data.get("matchedPreference") or "")
        return KioskProfile(
            document_id=doc.id,
            name=data.get("name") or data.get("nickname") or "Unknown",
            nfc_uid=nfc_uid,
            raw_matched_preference=matched_preference,
            matched_preference=matched_preference,
        )

    def start_match_listener(self, on_match):
        self.initialise()

        query = self.db.collection("matches").where("status", "==", "MATCHED")

        def on_snapshot(docs, changes, read_time):
            del docs, read_time

            for change in changes:
                if change.type.name not in {"ADDED", "MODIFIED"}:
                    continue

                match = self.build_kiosk_match(change.document)
                if match is not None:
                    on_match(match)

        return query.on_snapshot(on_snapshot)

    def build_kiosk_match(self, document):
        data = document.to_dict() or {}
        profiles = []

        for user in data.get("users") or []:
            if not isinstance(user, dict):
                continue

            nfc_uid = user.get("nfcUid")
            if not nfc_uid:
                continue

            matched_preference = str(user.get("matchedPreference") or "")

            profiles.append(
                KioskProfile(
                    document_id=user.get("profileId") or "",
                    name=(
                        user.get("name")
                        or user.get("nickname")
                        or user.get("displayName")
                        or user.get("firstName")
                        or user.get("username")
                        or f"profile-{str(user.get('profileId') or '')[:8]}"
                    ),
                    nfc_uid=nfc_uid,
                    raw_matched_preference=matched_preference,
                    matched_preference=matched_preference,
                )
            )

        if len(profiles) < 2:
            return None

        return KioskMatch(
            document_id=document.id,
            profiles=profiles[:2],
        )


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


def matched_preference_kind(value):
    raw = str(value or "").strip().lower()
    compact = raw.replace("\n", " ")
    token = compact.replace(" ", "_").replace("-", "_")

    if "no help" in compact:
        return "NO_HELP"
    if token == "light_help":
        return "SHORT_GAME"
    if "small ice" in compact or "ice breaker" in compact or "icebreaker" in compact:
        return "SMALL_ICEBREAKER"
    if "short game" in compact:
        return "SHORT_GAME"
    if "longer game" in compact or "long game" in compact:
        return "LONG_GAME"

    return "UNKNOWN"


def interaction_choice_kind(profile):
    return matched_preference_kind(profile.matched_preference)


def both_selected_no_help(left_profile, right_profile):
    return {
        interaction_choice_kind(left_profile),
        interaction_choice_kind(right_profile),
    } == {"NO_HELP"}


def both_selected_light_game(left_profile, right_profile):
    return interaction_choice_kind(left_profile) in {
        "SMALL_ICEBREAKER",
        "SHORT_GAME",
    } and interaction_choice_kind(right_profile) in {
        "SMALL_ICEBREAKER",
        "SHORT_GAME",
    }


def both_selected_long_game(left_profile, right_profile):
    return {
        interaction_choice_kind(left_profile),
        interaction_choice_kind(right_profile),
    } == {"LONG_GAME"}


def game_by_script(script):
    for game in GAMES:
        if game.script == script:
            return game

    raise ValueError(f"Unknown kiosk game script: {script}")


def assign_light_help_game(left_profile, right_profile):
    kinds = {
        interaction_choice_kind(left_profile),
        interaction_choice_kind(right_profile),
    }

    if kinds == {"SMALL_ICEBREAKER"}:
        variant = "small_small"
        options = [
            AssignedGame(game_by_script("tug_of_war"), points_to_win=1),
            AssignedGame(game_by_script("reaction_time"), points_to_win=2),
            AssignedGame(game_by_script("hot_potato"), hot_potato_seconds=6.0),
            AssignedGame(game_by_script("five_second_reaction"), points_to_win=1),
        ]
    elif kinds == {"SHORT_GAME"}:
        variant = "short_short"
        options = [
            AssignedGame(game_by_script("tug_of_war"), points_to_win=2),
            AssignedGame(game_by_script("reaction_time"), points_to_win=2),
            AssignedGame(game_by_script("hot_potato"), hot_potato_seconds=10.0),
            AssignedGame(game_by_script("five_second_reaction"), points_to_win=2),
        ]
    elif kinds == {"SMALL_ICEBREAKER", "SHORT_GAME"}:
        variant = "small_short"
        options = [
            AssignedGame(game_by_script("tug_of_war"), points_to_win=1),
            AssignedGame(game_by_script("reaction_time"), points_to_win=2),
            AssignedGame(game_by_script("hot_potato"), hot_potato_seconds=10.0),
            AssignedGame(game_by_script("five_second_reaction"), points_to_win=2),
        ]
    else:
        raise ValueError(f"Unsupported light-help game combination: {sorted(kinds)}")

    assigned = random.choice(options)
    print(
        f"Assigned {assigned.game.title} for {variant}: "
        f"points_to_win={assigned.points_to_win}, "
        f"hot_potato_seconds={assigned.hot_potato_seconds}"
    )
    return assigned


def assign_long_game(left_profile, right_profile):
    del left_profile, right_profile

    assigned = random.choice(
        [
            AssignedGame(game_by_script("darts")),
            AssignedGame(game_by_script("truth_or_dare")),
        ]
    )
    print(f"Assigned longer game: {assigned.game.title}")
    return assigned


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


def draw_no_help_coupon(surface):
    image = load_image("no_help_coupon.png", (WIDTH, HEIGHT))
    if image:
        surface.blit(image, (0, 0))
        return

    surface.fill(BLACK)
    draw_logo(surface, dark=False, force_white=True)
    draw_centered_text(
        surface,
        "HAVE A NICE THURSDAY",
        42,
        WHITE,
        (WIDTH // 2, HEIGHT // 2 - 40),
    )
    draw_centered_text(
        surface,
        "COLLECT AND REDEEM YOUR COUPONS",
        26,
        SOFT_PINK,
        (WIDTH // 2, HEIGHT // 2 + 52),
    )


def draw_game_over_coupon(surface):
    image = load_image("game_over_coupon.png", (WIDTH, HEIGHT))
    if image:
        surface.blit(image, (0, 0))
        return

    surface.fill(BLACK)
    draw_logo(surface, dark=False, force_white=True)
    draw_centered_text(
        surface,
        "GAME OVER",
        48,
        WHITE,
        (WIDTH // 2, HEIGHT // 2 - 34),
    )
    draw_centered_text(
        surface,
        "COLLECT AND REDEEM YOUR COUPONS",
        26,
        SOFT_PINK,
        (WIDTH // 2, HEIGHT // 2 + 72),
    )


def draw_scan_respective_wristbands(surface):
    image = load_image("scan_respective_wristbands.png", (WIDTH, HEIGHT))
    if image:
        surface.blit(image, (0, 0))
        return

    surface.fill(BLACK)
    draw_logo(surface, dark=False, force_white=True)
    draw_centered_text(
        surface,
        "SCAN YOUR RESPECTIVE",
        42,
        WHITE,
        (WIDTH // 2, HEIGHT // 2 - 84),
    )
    draw_centered_text(
        surface,
        "WRISTBANDS ON EITHER",
        42,
        WHITE,
        (WIDTH // 2, HEIGHT // 2 - 36),
    )
    draw_centered_text(
        surface,
        "SIDE TO BEGIN!",
        42,
        SOFT_PINK,
        (WIDTH // 2, HEIGHT // 2 + 12),
    )


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


def led_match_scan(strip, tick, left_ready, right_ready):
    pixels = {}
    pulse = (math.sin(tick * 8.0) + 1) / 2
    pulsing_pink = blend(PINK, SOFT_PINK, 0.25 + pulse * 0.65)
    solid_pink = SOFT_PINK

    for index in LEFT_LED_RANGE:
        pixels[index] = solid_pink if left_ready else pulsing_pink
    for index in RIGHT_LED_RANGE:
        pixels[index] = solid_pink if right_ready else pulsing_pink

    strip.set_pixels(pixels)


def release_hardware(buttons, strip):
    strip.clear()
    buttons.close()


def wait_for_both_buttons_latched(screen, buttons, game):
    left_seen = False
    right_seen = False
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

        if left_pressed and not left_was_pressed:
            left_seen = True
        if right_pressed and not right_was_pressed:
            right_seen = True

        draw_game_card(screen, game)
        pygame.display.flip()

        if left_seen and right_seen:
            wait_for_button_release(buttons)
            return

        left_was_pressed = left_pressed
        right_was_pressed = right_pressed
        time.sleep(0.02)


def wait_for_any_button(screen, buttons, draw):
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise KeyboardInterrupt
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                raise KeyboardInterrupt

        keys = pygame.key.get_pressed()
        left_pressed, right_pressed = buttons.states(keys)

        draw()
        pygame.display.flip()

        if left_pressed or right_pressed:
            wait_for_button_release(buttons)
            return

        time.sleep(0.02)


def wait_for_button_release(buttons):
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise KeyboardInterrupt
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                raise KeyboardInterrupt

        keys = pygame.key.get_pressed()
        left_pressed, right_pressed = buttons.states(keys)
        if not left_pressed and not right_pressed:
            return
        time.sleep(0.01)


def show_game_over(screen, seconds=3.0):
    started_at = time.monotonic()
    while time.monotonic() - started_at < seconds:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise KeyboardInterrupt
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                raise KeyboardInterrupt

        draw_game_over_coupon(screen)
        pygame.display.flip()
        time.sleep(0.02)


def dispense_token():
    if not TOKEN_DISPENSER_ENABLED:
        print("Token dispenser disabled.")
        return

    try:
        from dual_servo_relay_test import move_dual_servos

        print(
            "Dispensing token: dual servo sweep, then relay pulse "
            f"(left GPIO{TOKEN_LEFT_SERVO_PIN}, "
            f"right GPIO{TOKEN_RIGHT_SERVO_PIN}, "
            f"relay GPIO{TOKEN_RELAY_PIN})."
        )
        move_dual_servos(
            TOKEN_LEFT_SERVO_PIN,
            TOKEN_RIGHT_SERVO_PIN,
            TOKEN_RELAY_PIN,
        )
        print("Token dispense sequence complete.")
    except Exception as error:
        print(f"Token dispense failed: {error}")


def launch_game(assigned_game, screen, buttons, strip):
    game = assigned_game.game
    strip.clear()
    draw_game_card(screen, game)
    pygame.display.flip()
    wait_for_both_buttons_latched(screen, buttons, game)
    draw_rules_page(screen, game)
    pygame.display.flip()
    wait_for_any_button(
        screen,
        buttons,
        lambda: draw_rules_page(screen, game),
    )

    try:
        if game.script in SCREEN_GAMES:
            play_screen_game(
                game.script,
                screen,
                buttons.left,
                buttons.right,
                strip,
                points_to_win=assigned_game.points_to_win,
            )
        else:
            play_game(
                game.script,
                left_button=buttons.left,
                right_button=buttons.right,
                points_to_win=assigned_game.points_to_win,
                hot_potato_seconds=assigned_game.hot_potato_seconds,
            )
    finally:
        print("Game ended. Returning to Cue kiosk.")
        show_game_over(screen)
        dispense_token()


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
    match_lock = threading.RLock()
    pending_match = None
    current_match = None

    def on_match_received(match):
        nonlocal pending_match
        with match_lock:
            pending_match = match
        print(f"Kiosk match received: matches/{match.document_id}")

    match_watch = firebase_profiles.start_match_listener(on_match_received)

    state = "clock"
    left_ready = False
    right_ready = False
    left_nfc_uid = None
    right_nfc_uid = None
    left_profile = None
    right_profile = None
    kiosk_status = None
    debug_scan_mode = False
    both_buttons_hold_started = None
    previous_left = False
    previous_right = False

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
                with match_lock:
                    if pending_match is not None:
                        current_match = pending_match
                        pending_match = None
                        left_ready = False
                        right_ready = False
                        left_nfc_uid = None
                        right_nfc_uid = None
                        left_profile = None
                        right_profile = None
                        kiosk_status = None
                        debug_scan_mode = False
                        both_buttons_hold_started = None
                        if nfc_scanners is not None:
                            nfc_scanners.reset()
                        state = "scan_wristbands"
                        print(
                            "Entering wristband scan page for "
                            f"matches/{current_match.document_id}"
                        )

                if state == "clock":
                    if left_pressed and right_pressed:
                        if both_buttons_hold_started is None:
                            both_buttons_hold_started = now
                        elif now - both_buttons_hold_started >= DEBUG_SCAN_HOLD_SECONDS:
                            current_match = KioskMatch(
                                document_id="debug-button-match",
                                profiles=[],
                            )
                            left_ready = False
                            right_ready = False
                            left_nfc_uid = None
                            right_nfc_uid = None
                            left_profile = None
                            right_profile = None
                            kiosk_status = "Debug NFC scan mode"
                            debug_scan_mode = True
                            both_buttons_hold_started = None
                            if nfc_scanners is not None:
                                nfc_scanners.reset()
                            state = "scan_wristbands"
                            print(
                                "Debug NFC scan mode entered after holding both "
                                f"buttons for {DEBUG_SCAN_HOLD_SECONDS:.1f}s."
                            )
                    else:
                        both_buttons_hold_started = None

                if state == "clock":
                    draw_clock(screen)
                    led_ready(strip, now, False, False)

            elif state == "scan_wristbands":
                if left_scan_uid:
                    left_nfc_uid = left_scan_uid
                    print(f"LEFT NFC scanned: {left_nfc_uid}")
                    if debug_scan_mode:
                        left_profile = create_debug_profile("left", left_nfc_uid)
                    else:
                        left_profile = current_match.profile_for_nfc_uid(left_nfc_uid)

                    if left_profile is None:
                        left_ready = False
                        kiosk_status = "Left wristband is not in this match"
                    else:
                        left_ready = True
                        kiosk_status = (
                            f"Left: {left_profile.name} "
                            f"({left_profile.matched_preference})"
                        )

                if right_scan_uid:
                    right_nfc_uid = right_scan_uid
                    print(f"RIGHT NFC scanned: {right_nfc_uid}")
                    if debug_scan_mode:
                        right_profile = create_debug_profile("right", right_nfc_uid)
                    else:
                        right_profile = current_match.profile_for_nfc_uid(right_nfc_uid)

                    if right_profile is None:
                        right_ready = False
                        kiosk_status = "Right wristband is not in this match"
                    else:
                        right_ready = True
                        kiosk_status = (
                            f"Right: {right_profile.name} "
                            f"({right_profile.matched_preference})"
                        )

                draw_scan_respective_wristbands(screen)
                led_match_scan(strip, now, left_ready, right_ready)

                if left_ready and right_ready:
                    pygame.display.flip()

                    if left_nfc_uid == right_nfc_uid:
                        kiosk_status = "Scan two different wristbands"
                        draw_waiting(screen, False, False, kiosk_status)
                        pygame.display.flip()
                        time.sleep(1.5)
                        left_ready = False
                        right_ready = False
                        left_nfc_uid = None
                        right_nfc_uid = None
                        left_profile = None
                        right_profile = None
                        kiosk_status = None
                        if nfc_scanners is not None:
                            nfc_scanners.reset()
                    elif both_selected_no_help(left_profile, right_profile):
                        print("Both wristbands selected no help. Showing coupon page.")
                        strip.clear()
                        state = "no_help_coupon"
                    elif both_selected_light_game(left_profile, right_profile):
                        assigned_game = assign_light_help_game(
                            left_profile,
                            right_profile,
                        )
                        pygame.display.flip()
                        launch_game(assigned_game, screen, buttons, strip)
                        reset_matching_hub()
                        state = "clock"
                        current_match = None
                        left_ready = False
                        right_ready = False
                        left_nfc_uid = None
                        right_nfc_uid = None
                        left_profile = None
                        right_profile = None
                        kiosk_status = None
                        debug_scan_mode = False
                        if nfc_scanners is not None:
                            nfc_scanners.reset()
                    elif both_selected_long_game(left_profile, right_profile):
                        assigned_game = assign_long_game(
                            left_profile,
                            right_profile,
                        )
                        pygame.display.flip()
                        launch_game(assigned_game, screen, buttons, strip)
                        reset_matching_hub()
                        state = "clock"
                        current_match = None
                        left_ready = False
                        right_ready = False
                        left_nfc_uid = None
                        right_nfc_uid = None
                        left_profile = None
                        right_profile = None
                        kiosk_status = None
                        debug_scan_mode = False
                        if nfc_scanners is not None:
                            nfc_scanners.reset()
                    else:
                        kiosk_status = (
                            "Game assignment flow coming next: "
                            f"{left_profile.matched_preference} + "
                            f"{right_profile.matched_preference}"
                        )
                        print(kiosk_status)
                        state = "game_assignment_pending"

            elif state == "no_help_coupon":
                draw_no_help_coupon(screen)
                strip.clear()

            elif state == "game_assignment_pending":
                draw_waiting(screen, True, True, kiosk_status)
                led_ready(strip, now, True, True)

            previous_left = left_pressed
            previous_right = right_pressed

            pygame.display.flip()
            clock.tick(FPS)

    finally:
        match_watch.unsubscribe()
        release_hardware(buttons, strip)
        pygame.quit()


if __name__ == "__main__":
    try:
        import pygame
    except ImportError:
        print("pygame is required. Install it with: pip3 install pygame --break-system-packages")
        raise

    run()
