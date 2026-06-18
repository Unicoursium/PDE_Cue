LED_COUNT = 55

# Physical strip layout, using zero-based indexes in code:
# - Left half, top-to-bottom: 9 -> 35
# - Center: 36
# - Right half, top-to-bottom: 8 -> 1, then 55 -> 37
CENTER_LED = 35

LEFT_SIDE_TOP_TO_BOTTOM = list(range(8, 35))
LEFT_SIDE_BOTTOM_TO_TOP = list(reversed(LEFT_SIDE_TOP_TO_BOTTOM))

RIGHT_SIDE_TOP_TO_BOTTOM = list(range(7, -1, -1)) + list(range(54, 35, -1))
RIGHT_SIDE_BOTTOM_TO_TOP = list(reversed(RIGHT_SIDE_TOP_TO_BOTTOM))

LEFT_SIDE = LEFT_SIDE_TOP_TO_BOTTOM
RIGHT_SIDE = RIGHT_SIDE_TOP_TO_BOTTOM

# Tug of war is modelled as one continuous visual path:
# left top -> left bottom -> center -> right bottom -> right top.
TUG_OF_WAR_PATH = (
    LEFT_SIDE_TOP_TO_BOTTOM
    + [CENTER_LED]
    + RIGHT_SIDE_BOTTOM_TO_TOP
)
TUG_OF_WAR_CENTER_POSITION = len(LEFT_SIDE_TOP_TO_BOTTOM)


def side_leds(side):
    if side == "left":
        return LEFT_SIDE
    if side == "right":
        return RIGHT_SIDE
    raise ValueError(f"Unknown side: {side}")


def score_leds(side, count):
    """Return LEDs from the bottom-middle outward for score/progress displays."""
    count = max(0, min(count, len(LEFT_SIDE_BOTTOM_TO_TOP)))

    if side == "left":
        return LEFT_SIDE_BOTTOM_TO_TOP[:count]
    if side == "right":
        return RIGHT_SIDE_BOTTOM_TO_TOP[:count]
    raise ValueError(f"Unknown side: {side}")
