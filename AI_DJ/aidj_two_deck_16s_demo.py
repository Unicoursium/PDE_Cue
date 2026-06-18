from __future__ import annotations

import argparse
import time
from dataclasses import dataclass

from virtualdj_soundcloud_automix import (
    VirtualDJTrack,
    check_virtualdj_connection,
    get_selected_virtualdj_track,
    vdj_execute,
    vdj_query,
    vdj_quote,
    wait_for_search_result,
)


TRACK_A_QUERY = "Glitchery Heavenly Key"
TRACK_B_QUERY = "2hollis Poster Boy"
SEGMENT_SECONDS = 16.0
FADE_SECONDS = 4.0
FADE_STEPS = 20
MAX_SEGMENTS_PER_DECK = 40


@dataclass
class LoadedDeck:
    deck: int
    query: str
    track: VirtualDJTrack


def search_and_load_to_deck(query: str, deck: int) -> LoadedDeck:
    print()
    print(f"Searching for deck {deck}: {query}")
    vdj_execute("clear_search")
    time.sleep(0.3)
    vdj_execute(f"search {vdj_quote(query)}")

    selected = wait_for_search_result()
    print(
        f"Selected for deck {deck}: "
        f"{selected.artist} - {selected.title} [{selected.filepath}]"
    )

    vdj_execute(f"deck {deck} load")
    time.sleep(1.0)

    loaded = read_deck_track(deck)
    print(
        f"Loaded deck {deck}: "
        f"{loaded.artist or selected.artist} - {loaded.title or selected.title}"
    )
    return LoadedDeck(deck=deck, query=query, track=loaded if loaded.is_valid else selected)


def read_deck_track(deck: int) -> VirtualDJTrack:
    return VirtualDJTrack(
        title=query_first(
            [
                f"deck {deck} get_loaded_song 'title'",
                f"deck {deck} get_song 'title'",
            ],
            default="",
        ),
        artist=query_first(
            [
                f"deck {deck} get_loaded_song 'artist'",
                f"deck {deck} get_song 'artist'",
            ],
            default="",
        ),
        filepath=query_first(
            [
                f"deck {deck} get_loaded_song 'filepath'",
                f"deck {deck} get_song 'filepath'",
            ],
            default="",
        ),
    )


def query_first(scripts: list[str], default: str = "") -> str:
    for script in scripts:
        try:
            value = vdj_query(script).strip()
        except Exception:
            continue

        if value and not value.lower().startswith("error:"):
            return value

    return default


def query_float_first(scripts: list[str]) -> float | None:
    for script in scripts:
        value = query_first([script])
        if not value:
            continue

        try:
            return float(value)
        except ValueError:
            continue

    return None


def deck_position(deck: int) -> float | None:
    return query_float_first(
        [
            f"deck {deck} get_position",
            f"deck {deck} song_pos",
            f"deck {deck} get_song_pos",
        ]
    )


def deck_is_finished(deck: int) -> bool:
    position = deck_position(deck)
    return position is not None and position >= 0.985


def stop_all_decks() -> None:
    for deck in (1, 2):
        try:
            vdj_execute(f"deck {deck} pause")
        except Exception:
            pass


def set_deck_volume(deck: int, volume: float) -> None:
    volume = max(0.0, min(1.0, volume))
    percent = round(volume * 100)
    vdj_execute(f"deck {deck} volume {percent}%")


def crossfade(from_deck: int, to_deck: int, seconds: float) -> None:
    print(f"Crossfading deck {from_deck} -> deck {to_deck} over {seconds:g}s")
    set_deck_volume(to_deck, 0.0)
    vdj_execute(f"deck {to_deck} play")

    steps = max(1, FADE_STEPS)
    delay = seconds / steps if seconds > 0 else 0

    for step in range(steps + 1):
        amount = step / steps
        set_deck_volume(from_deck, 1.0 - amount)
        set_deck_volume(to_deck, amount)
        if delay:
            time.sleep(delay)

    vdj_execute(f"deck {from_deck} pause")
    set_deck_volume(from_deck, 1.0)
    set_deck_volume(to_deck, 1.0)
    time.sleep(0.1)


def play_segment(deck: int, seconds: float, fade_out=False, next_deck=None, fade_seconds=0.0) -> bool:
    print(f"Playing deck {deck} for {seconds:g}s")
    set_deck_volume(deck, 1.0)
    vdj_execute(f"deck {deck} play")

    hold_seconds = max(0.0, seconds - (fade_seconds if fade_out and next_deck else 0.0))

    started_at = time.monotonic()
    while time.monotonic() - started_at < hold_seconds:
        if deck_is_finished(deck):
            print(f"Deck {deck} appears to be finished.")
            vdj_execute(f"deck {deck} pause")
            return True
        time.sleep(0.25)

    if fade_out and next_deck is not None:
        crossfade(deck, next_deck, fade_seconds)
    else:
        vdj_execute(f"deck {deck} pause")
        time.sleep(0.25)

    return deck_is_finished(deck)


def run_demo(
    track_a_query: str,
    track_b_query: str,
    segment_seconds: float,
    fade_seconds: float,
) -> None:
    print("Cue AIDJ two-deck 16s demo")
    print("=" * 34)
    check_virtualdj_connection()

    print("Stopping decks before loading demo tracks.")
    stop_all_decks()

    deck_a = search_and_load_to_deck(track_a_query, deck=1)
    deck_b = search_and_load_to_deck(track_b_query, deck=2)
    set_deck_volume(1, 1.0)
    set_deck_volume(2, 1.0)

    print()
    print("Demo loaded:")
    print(f"  Deck A: {deck_a.track.artist} - {deck_a.track.title}")
    print(f"  Deck B: {deck_b.track.artist} - {deck_b.track.title}")
    print()

    for segment_index in range(MAX_SEGMENTS_PER_DECK):
        a_done = deck_is_finished(1)
        b_done = deck_is_finished(2)

        if a_done and b_done:
            print("Both decks are finished.")
            break

        if not a_done:
            play_segment(
                1,
                segment_seconds,
                fade_out=not b_done,
                next_deck=2,
                fade_seconds=fade_seconds,
            )

        b_done = deck_is_finished(2)
        if not b_done:
            a_done = deck_is_finished(1)
            play_segment(
                2,
                segment_seconds,
                fade_out=not a_done,
                next_deck=1,
                fade_seconds=fade_seconds,
            )
    else:
        print(
            "Reached the safety segment limit. "
            "Stopping so the demo cannot run forever."
        )

    stop_all_decks()
    print("Demo complete.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search two tracks in VirtualDJ, load deck A/B, and alternate 16s playback."
    )
    parser.add_argument("--track-a", default=TRACK_A_QUERY)
    parser.add_argument("--track-b", default=TRACK_B_QUERY)
    parser.add_argument("--segment-seconds", type=float, default=SEGMENT_SECONDS)
    parser.add_argument("--fade-seconds", type=float, default=FADE_SECONDS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_demo(args.track_a, args.track_b, args.segment_seconds, args.fade_seconds)


if __name__ == "__main__":
    main()
