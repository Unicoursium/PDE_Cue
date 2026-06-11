import time
import math
import random

import pygame


WIDTH = 640
HEIGHT = 480
TARGET_SECONDS = 5.0
LED_COUNT = 40
HALF_LED_COUNT = LED_COUNT // 2

BG = (34, 34, 34)
WHITE = (255, 255, 255)
MUTED = (145, 145, 145)
LEFT_COLOR = (222, 55, 133)
RIGHT_COLOR = (42, 174, 230)
WIN_COLOR = (124, 235, 168)
DART_RED = (214, 62, 70)
DART_GREEN = (52, 145, 88)
DART_CREAM = (236, 220, 178)
DART_BLACK = (28, 28, 30)

DART_NUMBERS = [
    20, 1, 18, 4, 13, 6, 10, 15, 2, 17,
    3, 19, 7, 16, 8, 11, 14, 9, 12, 5,
]

DART_CENTER = (420, 260)
DART_RADIUS = 155

TRUTH_QUESTIONS = [
    "What is something you wish people understood about you?",
    "What was your first impression of the other player?",
    "What is the most embarrassing song you secretly love?",
    "What is the boldest thing you have ever done?",
    "What is one habit you would like to change?",
    "Who was your first celebrity crush?",
    "What is the funniest lie you told as a child?",
    "What is something you are proud of but rarely mention?",
    "What is your most irrational fear?",
    "What is the worst date you have ever been on?",
    "What is the nicest compliment you have ever received?",
    "What is a skill you pretend to be better at than you are?",
    "What is the last thing that made you cry?",
    "What is one thing on your bucket list?",
    "What is the strangest dream you remember?",
    "What is your biggest dating dealbreaker?",
    "What is a secret talent you have?",
    "What is the most spontaneous thing you have ever done?",
    "What is something you have never told your parents?",
    "If you could relive one day, which day would it be?",
]

DARES = [
    "Give the other player your best dramatic movie speech.",
    "Dance without music for twenty seconds.",
    "Speak in an accent until your next turn.",
    "Let the other player choose a pose for you to hold.",
    "Do your best impression of a celebrity.",
    "Sing the chorus of a song chosen by the other player.",
    "Give the other player three sincere compliments.",
    "Pretend to be a news reporter covering this moment.",
    "Act like a robot until your next turn.",
    "Make up a short poem about the other player.",
    "Do ten seconds of your best runway walk.",
    "Let the other player rename you for the next three turns.",
    "Tell a joke and keep a straight face.",
    "Recreate your favourite emoji using only your face.",
    "Do your best victory celebration.",
    "Describe the other player like a nature documentary.",
    "Invent and perform a new handshake together.",
    "Hum a song until the other player guesses it.",
    "Give a one-minute motivational speech about something silly.",
    "Act out an animal chosen by the other player.",
]


def font(size, bold=True):
    return pygame.font.SysFont("Arial", size, bold=bold)


def draw_text(surface, text, size, color, position, anchor="center", bold=True):
    rendered = font(size, bold).render(text, True, color)
    rect = rendered.get_rect()
    setattr(rect, anchor, position)
    surface.blit(rendered, rect)


def draw_wrapped_text(surface, text, size, color, rect, bold=True, line_gap=8):
    text_font = font(size, bold)
    words = text.split()
    lines = []
    current = []

    for word in words:
        candidate = " ".join(current + [word])
        if text_font.size(candidate)[0] <= rect.width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))

    total_height = len(lines) * text_font.get_linesize() + max(0, len(lines) - 1) * line_gap
    y = rect.centery - total_height // 2
    for line in lines:
        rendered = text_font.render(line, True, color)
        surface.blit(rendered, rendered.get_rect(midtop=(rect.centerx, y)))
        y += text_font.get_linesize() + line_gap


def format_timer(elapsed):
    centiseconds = int(elapsed * 100) % 100
    seconds = int(elapsed)
    return f"{seconds}:{centiseconds:02d}"


def format_error(elapsed):
    difference_ms = round(abs(elapsed - TARGET_SECONDS) * 1000)
    return f"{difference_ms} ms away"


def pump_events():
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            raise KeyboardInterrupt
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            raise KeyboardInterrupt


def button_pressed(button, keyboard_key):
    keys = pygame.key.get_pressed()
    return keys[keyboard_key] or (button is not None and button.is_pressed)


def wait_for_release(button, keyboard_key):
    while button_pressed(button, keyboard_key):
        pump_events()
        time.sleep(0.01)


def wait_for_press(button, keyboard_key, draw):
    while not button_pressed(button, keyboard_key):
        pump_events()
        draw()
        pygame.display.flip()
        time.sleep(0.01)


def draw_timer_game(
    screen,
    active_side,
    elapsed,
    left_result=None,
    right_result=None,
    headline=None,
):
    screen.fill(BG)

    left_active = active_side == "left"
    right_active = active_side == "right"
    draw_text(
        screen,
        "LEFT PLAYER",
        24,
        LEFT_COLOR if left_active else MUTED,
        (32, 34),
        anchor="topleft",
    )
    draw_text(
        screen,
        "RIGHT PLAYER",
        24,
        RIGHT_COLOR if right_active else MUTED,
        (WIDTH - 32, 34),
        anchor="topright",
    )

    if left_result is not None:
        draw_text(
            screen,
            format_error(left_result),
            22,
            LEFT_COLOR,
            (32, 72),
            anchor="topleft",
        )
    if right_result is not None:
        draw_text(
            screen,
            format_error(right_result),
            22,
            RIGHT_COLOR,
            (WIDTH - 32, 72),
            anchor="topright",
        )

    draw_text(screen, format_timer(elapsed), 132, WHITE, (WIDTH // 2, HEIGHT // 2))

    if headline:
        draw_text(screen, headline, 34, WIN_COLOR, (WIDTH // 2, HEIGHT - 58))


def run_player_turn(screen, side, button, keyboard_key, left_result, right_result):
    wait_for_release(button, keyboard_key)

    def draw_ready():
        draw_timer_game(
            screen,
            side,
            0.0,
            left_result=left_result,
            right_result=right_result,
        )

    wait_for_press(button, keyboard_key, draw_ready)
    wait_for_release(button, keyboard_key)
    started_at = time.monotonic()

    while True:
        pump_events()
        elapsed = time.monotonic() - started_at
        draw_timer_game(
            screen,
            side,
            elapsed,
            left_result=left_result,
            right_result=right_result,
        )
        pygame.display.flip()

        if button_pressed(button, keyboard_key):
            stopped_at = time.monotonic()
            wait_for_release(button, keyboard_key)
            return stopped_at - started_at

        time.sleep(0.005)


def play_five_second_reaction(screen, left_button, right_button, strip):
    left_result = run_player_turn(
        screen,
        "left",
        left_button,
        pygame.K_LEFT,
        None,
        None,
    )

    draw_timer_game(
        screen,
        "right",
        0.0,
        left_result=left_result,
    )
    pygame.display.flip()
    time.sleep(1.0)

    right_result = run_player_turn(
        screen,
        "right",
        right_button,
        pygame.K_RIGHT,
        left_result,
        None,
    )

    left_error = abs(left_result - TARGET_SECONDS)
    right_error = abs(right_result - TARGET_SECONDS)

    if abs(left_error - right_error) < 0.0005:
        headline = "TIE"
        winner_pixels = {index: WIN_COLOR for index in range(LED_COUNT)}
    elif left_error < right_error:
        headline = "LEFT PLAYER WINS"
        winner_pixels = {index: LEFT_COLOR for index in range(HALF_LED_COUNT)}
    else:
        headline = "RIGHT PLAYER WINS"
        winner_pixels = {
            index: RIGHT_COLOR
            for index in range(HALF_LED_COUNT, LED_COUNT)
        }

    strip.set_pixels(winner_pixels)
    result_started = time.monotonic()
    while time.monotonic() - result_started < 5.0:
        pump_events()
        draw_timer_game(
            screen,
            None,
            right_result,
            left_result=left_result,
            right_result=right_result,
            headline=headline,
        )
        pygame.display.flip()
        time.sleep(0.02)

    strip.clear()


def dart_score(x, y, center, radius):
    dx = x - center[0]
    dy = y - center[1]
    distance = math.hypot(dx, dy)

    if distance > radius:
        return 0, "MISS"
    if distance <= radius * 0.045:
        return 50, "BULLSEYE"
    if distance <= radius * 0.095:
        return 25, "BULL"

    angle = (math.degrees(math.atan2(dx, -dy)) + 360) % 360
    number = DART_NUMBERS[int((angle + 9) // 18) % 20]

    if radius * 0.50 <= distance <= radius * 0.58:
        return number * 3, f"TRIPLE {number}"
    if radius * 0.88 <= distance <= radius:
        return number * 2, f"DOUBLE {number}"
    return number, str(number)


def draw_dartboard(screen, center, radius):
    for sector_index, number in enumerate(DART_NUMBERS):
        start_angle = math.radians(sector_index * 18 - 99)
        end_angle = math.radians((sector_index + 1) * 18 - 99)
        points = [center]
        for step in range(5):
            angle = start_angle + (end_angle - start_angle) * step / 4
            points.append(
                (
                    center[0] + math.cos(angle) * radius,
                    center[1] + math.sin(angle) * radius,
                )
            )
        color = DART_CREAM if sector_index % 2 == 0 else DART_BLACK
        pygame.draw.polygon(screen, color, points)

        number_angle = math.radians(sector_index * 18 - 90)
        label_position = (
            center[0] + math.cos(number_angle) * (radius + 18),
            center[1] + math.sin(number_angle) * (radius + 18),
        )
        draw_text(screen, str(number), 15, WHITE, label_position)

    for ring_radius, width in (
        (radius, 8),
        (radius * 0.88, 7),
        (radius * 0.58, 7),
        (radius * 0.50, 7),
    ):
        pygame.draw.circle(screen, DART_RED, center, int(ring_radius), width)

    pygame.draw.circle(screen, DART_GREEN, center, int(radius * 0.095))
    pygame.draw.circle(screen, DART_RED, center, int(radius * 0.045))
    pygame.draw.circle(screen, WHITE, center, radius, 2)


def moving_axis_value(started_at, minimum, maximum, speed):
    span = maximum - minimum
    phase = ((time.monotonic() - started_at) * speed) % (span * 2)
    if phase > span:
        phase = span * 2 - phase
    return minimum + phase


def wait_for_dart_lock(screen, button, keyboard_key, draw):
    wait_for_release(button, keyboard_key)
    started_at = time.monotonic()

    while True:
        pump_events()
        value = draw(started_at)
        pygame.display.flip()

        if button_pressed(button, keyboard_key):
            wait_for_release(button, keyboard_key)
            return value

        time.sleep(0.008)


def draw_darts_scene(
    screen,
    scores,
    active_side,
    aim_x=None,
    aim_y=None,
    last_throw=None,
    message=None,
):
    screen.fill(BG)
    center = DART_CENTER
    radius = DART_RADIUS

    draw_text(screen, "DARTS", 28, WHITE, (22, 28), anchor="topleft")

    draw_text(
        screen,
        "LEFT PLAYER",
        20,
        LEFT_COLOR if active_side == "left" else MUTED,
        (22, 112),
        anchor="topleft",
    )
    draw_text(
        screen,
        str(scores["left"]),
        62,
        LEFT_COLOR,
        (22, 138),
        anchor="topleft",
    )
    draw_text(
        screen,
        "RIGHT PLAYER",
        20,
        RIGHT_COLOR if active_side == "right" else MUTED,
        (22, 270),
        anchor="topleft",
    )
    draw_text(
        screen,
        str(scores["right"]),
        62,
        RIGHT_COLOR,
        (22, 296),
        anchor="topleft",
    )

    draw_dartboard(screen, center, radius)

    if aim_x is not None:
        pygame.draw.line(
            screen,
            LEFT_COLOR if active_side == "left" else RIGHT_COLOR,
            (aim_x, center[1] - radius),
            (aim_x, center[1] + radius),
            3,
        )
    if aim_y is not None:
        pygame.draw.line(
            screen,
            LEFT_COLOR if active_side == "left" else RIGHT_COLOR,
            (center[0] - radius, aim_y),
            (center[0] + radius, aim_y),
            3,
        )
    if last_throw is not None:
        pygame.draw.circle(screen, WHITE, last_throw, 7, 2)
        pygame.draw.circle(screen, DART_RED, last_throw, 2)
    if message:
        message_surface = font(22).render(message, True, WHITE)
        message_rect = message_surface.get_rect(center=(DART_CENTER[0], 30))
        background_rect = message_rect.inflate(24, 12)
        pygame.draw.rect(screen, BG, background_rect, border_radius=6)
        screen.blit(message_surface, message_rect)


def show_darts_score_leds(strip, scores):
    left_count = math.ceil(scores["left"] / 301 * HALF_LED_COUNT)
    right_count = math.ceil(scores["right"] / 301 * HALF_LED_COUNT)
    pixels = {}

    for index in range(left_count):
        pixels[index] = LEFT_COLOR
    for index in range(right_count):
        pixels[HALF_LED_COUNT + index] = RIGHT_COLOR

    strip.set_pixels(pixels)


def play_darts(screen, left_button, right_button, strip):
    scores = {"left": 301, "right": 301}
    active_side = "left"
    board_center = DART_CENTER
    board_radius = DART_RADIUS
    min_x = board_center[0] - board_radius
    max_x = board_center[0] + board_radius
    min_y = board_center[1] - board_radius
    max_y = board_center[1] + board_radius
    show_darts_score_leds(strip, scores)

    while scores["left"] > 0 and scores["right"] > 0:
        button = left_button if active_side == "left" else right_button
        keyboard_key = pygame.K_LEFT if active_side == "left" else pygame.K_RIGHT

        locked_x = wait_for_dart_lock(
            screen,
            button,
            keyboard_key,
            lambda started_at: _draw_and_return(
                screen,
                scores,
                active_side,
                aim_x=moving_axis_value(started_at, min_x, max_x, 145),
            ),
        )

        locked_y = wait_for_dart_lock(
            screen,
            button,
            keyboard_key,
            lambda started_at: _draw_and_return(
                screen,
                scores,
                active_side,
                aim_x=locked_x,
                aim_y=moving_axis_value(started_at, min_y, max_y, 130),
            ),
        )

        throw = (round(locked_x), round(locked_y))
        points, label = dart_score(*throw, board_center, board_radius)
        remaining = scores[active_side] - points

        if remaining < 0:
            message = f"{label} - BUST"
        else:
            scores[active_side] = remaining
            message = f"{label}  -{points}"

        show_darts_score_leds(strip, scores)

        shown_at = time.monotonic()
        while time.monotonic() - shown_at < 1.4:
            pump_events()
            draw_darts_scene(
                screen,
                scores,
                active_side,
                last_throw=throw,
                message=message,
            )
            pygame.display.flip()
            time.sleep(0.02)

        if scores[active_side] == 0:
            break
        active_side = "right" if active_side == "left" else "left"

    winner = active_side
    strip.set_pixels(
        {
            index: LEFT_COLOR if winner == "left" else RIGHT_COLOR
            for index in (
                range(HALF_LED_COUNT)
                if winner == "left"
                else range(HALF_LED_COUNT, LED_COUNT)
            )
        }
    )
    result_started = time.monotonic()
    while time.monotonic() - result_started < 5.0:
        pump_events()
        draw_darts_scene(
            screen,
            scores,
            winner,
            message=f"{winner.upper()} PLAYER WINS",
        )
        pygame.display.flip()
        time.sleep(0.02)
    strip.clear()


def _draw_and_return(screen, scores, active_side, aim_x=None, aim_y=None):
    draw_darts_scene(
        screen,
        scores,
        active_side,
        aim_x=aim_x,
        aim_y=aim_y,
    )
    return aim_x if aim_y is None else aim_y


def new_truth_or_dare():
    if random.choice((True, False)):
        return "TRUTH", random.choice(TRUTH_QUESTIONS), LEFT_COLOR
    return "DARE", random.choice(DARES), RIGHT_COLOR


def draw_truth_or_dare(screen, active_side, prompt_type, prompt, hold_seconds):
    screen.fill(BG)
    active_color = LEFT_COLOR if active_side == "left" else RIGHT_COLOR
    player_name = "LEFT PLAYER" if active_side == "left" else "RIGHT PLAYER"

    draw_text(screen, player_name, 26, active_color, (28, 26), anchor="topleft")
    draw_text(screen, prompt_type, 42, active_color, (WIDTH // 2, 92))
    draw_wrapped_text(
        screen,
        prompt,
        32,
        WHITE,
        pygame.Rect(52, 130, WIDTH - 104, 210),
    )

    bar_rect = pygame.Rect(72, 390, WIDTH - 144, 24)
    pygame.draw.rect(screen, (76, 76, 78), bar_rect, border_radius=8)
    progress = min(1.0, hold_seconds / 3.0)
    if progress > 0:
        pygame.draw.rect(
            screen,
            active_color,
            pygame.Rect(bar_rect.x, bar_rect.y, int(bar_rect.width * progress), bar_rect.height),
            border_radius=8,
        )
    if hold_seconds < 3.0:
        instruction = f"Hold both buttons to skip  {hold_seconds:.1f}/3.0s"
    else:
        instruction = f"New prompt - keep holding to exit  {hold_seconds:.1f}/6.0s"
    draw_text(screen, instruction, 18, MUTED, (WIDTH // 2, 438))


def play_truth_or_dare(screen, left_button, right_button, strip):
    active_side = "left"
    prompt_type, prompt, _ = new_truth_or_dare()
    both_hold_started = None
    skip_triggered = False
    left_was_pressed = False
    right_was_pressed = False

    wait_for_release(left_button, pygame.K_LEFT)
    wait_for_release(right_button, pygame.K_RIGHT)

    while True:
        pump_events()
        left_now = button_pressed(left_button, pygame.K_LEFT)
        right_now = button_pressed(right_button, pygame.K_RIGHT)
        both_pressed = left_now and right_now

        if both_pressed:
            if both_hold_started is None:
                both_hold_started = time.monotonic()
            hold_seconds = time.monotonic() - both_hold_started

            if hold_seconds >= 3.0 and not skip_triggered:
                prompt_type, prompt, _ = new_truth_or_dare()
                skip_triggered = True
            if hold_seconds >= 6.0:
                strip.clear()
                return
        else:
            hold_seconds = 0.0
            both_hold_started = None
            skip_triggered = False

            current_edge = (
                active_side == "left"
                and left_now
                and not left_was_pressed
            ) or (
                active_side == "right"
                and right_now
                and not right_was_pressed
            )
            if current_edge:
                active_side = "right" if active_side == "left" else "left"
                prompt_type, prompt, _ = new_truth_or_dare()

        active_pixels = {
            index: LEFT_COLOR if active_side == "left" else RIGHT_COLOR
            for index in (
                range(HALF_LED_COUNT)
                if active_side == "left"
                else range(HALF_LED_COUNT, LED_COUNT)
            )
        }
        strip.set_pixels(active_pixels)
        draw_truth_or_dare(
            screen,
            active_side,
            prompt_type,
            prompt,
            hold_seconds,
        )
        pygame.display.flip()

        left_was_pressed = left_now
        right_was_pressed = right_now
        time.sleep(0.02)


def play_screen_game(game_name, screen, left_button, right_button, strip):
    if game_name == "five_second_reaction":
        play_five_second_reaction(screen, left_button, right_button, strip)
        return
    if game_name == "darts":
        play_darts(screen, left_button, right_button, strip)
        return
    if game_name == "truth_or_dare":
        play_truth_or_dare(screen, left_button, right_button, strip)
        return

    raise ValueError(f"Unknown screen game: {game_name}")
