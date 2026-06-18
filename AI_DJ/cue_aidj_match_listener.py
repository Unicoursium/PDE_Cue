from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from os import getenv
from pathlib import Path
from typing import Any

from aidj_two_deck_16s_demo import (
    MAX_SEGMENTS_PER_DECK,
    crossfade,
    deck_is_finished,
    play_segment,
    search_and_load_to_deck,
    set_deck_volume,
    stop_all_decks,
)
from firebase_virtualdj_automix_listener import (
    CLEAR_AUTOMIX_ON_START,
    SERVICE_ACCOUNT_PATH,
    START_AUTOMIX_AFTER_ADD,
    check_virtualdj_connection,
    clean_track_title,
    load_dotenv,
    start_automix_if_needed,
    vdj_execute,
    vdj_query,
    vdj_quote,
    wait_for_search_result,
)


SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

MATCHES_COLLECTION = getenv("AIDJ_MATCHES_COLLECTION", "matches")
MATCH_STATUS_FILTER = getenv("AIDJ_MATCH_STATUS", "MATCHED")
PLAYLIST_PATH = Path(getenv("AIDJ_PLAYLIST_PATH", str(SCRIPT_DIR / "aidj_playlist.txt")))
STATE_PATH = Path(getenv("AIDJ_MATCH_STATE_PATH", str(SCRIPT_DIR / "processed_aidj_matches.json")))
SEGMENT_SECONDS = float(getenv("AIDJ_MATCH_SEGMENT_SECONDS", "16"))
FADE_SECONDS = float(getenv("AIDJ_MATCH_FADE_SECONDS", "4"))
TTS_ENABLED = getenv("AIDJ_TTS_ENABLED", "1").lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class MatchUser:
    profile_id: str
    name: str
    soundcloud_track: dict[str, Any] | None

    @property
    def has_song(self) -> bool:
        return isinstance(self.soundcloud_track, dict) and bool(self.soundcloud_track.get("url"))

    @property
    def search_query(self) -> str:
        track = self.soundcloud_track or {}
        title = str(track.get("title") or "").strip()
        artists = str(track.get("artists") or "").strip()
        clean_title = clean_track_title(title, artists)
        return f"{artists} {clean_title}".strip() or str(track.get("url") or "").strip()


@dataclass(frozen=True)
class MatchCue:
    match_id: str
    users: tuple[MatchUser, MatchUser]


state_lock = threading.RLock()
processed_match_ids: set[str] = set()
queued_match_ids: set[str] = set()
work_queue: queue.Queue[MatchCue | None] = queue.Queue()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_processed_state() -> None:
    if not STATE_PATH.exists():
        return

    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read state file {STATE_PATH}: {exc}")
        return

    ids = payload.get("processedMatchIds", [])
    if isinstance(ids, list):
        processed_match_ids.update(str(match_id) for match_id in ids)


def save_processed_state() -> None:
    STATE_PATH.write_text(
        json.dumps(
            {
                "updatedAt": utc_now_iso(),
                "processedMatchIds": sorted(processed_match_ids),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def mark_processed(match_id: str) -> None:
    with state_lock:
        processed_match_ids.add(match_id)
        queued_match_ids.discard(match_id)
        save_processed_state()


def mark_not_queued(match_id: str) -> None:
    with state_lock:
        queued_match_ids.discard(match_id)


def read_playlist_queries() -> list[str]:
    if not PLAYLIST_PATH.exists():
        print(f"Playlist file not found yet: {PLAYLIST_PATH}")
        return []

    queries = []
    for raw_line in PLAYLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            queries.append(line)

    return queries


def search_and_add_query_to_automix(query: str) -> None:
    print(f"Adding playlist track to Automix: {query}")
    vdj_execute("clear_search")
    time.sleep(0.25)
    vdj_execute(f"search {vdj_quote(query)}")
    selected = wait_for_search_result()
    print(f"  Selected: {selected.artist} - {selected.title} [{selected.filepath}]")
    vdj_execute("playlist_add")
    time.sleep(0.2)


def load_background_playlist() -> None:
    queries = read_playlist_queries()
    if not queries:
        print("No background playlist entries loaded.")
        return

    if CLEAR_AUTOMIX_ON_START:
        vdj_execute("sideview 'automix'")
        vdj_execute("playlist_clear")
        print("Cleared VirtualDJ Automix list.")

    for query in queries:
        try:
            search_and_add_query_to_automix(query)
        except Exception as exc:
            print(f"Could not add playlist track {query!r}: {exc}")

    if START_AUTOMIX_AFTER_ADD:
        start_automix_if_needed()


def automix_is_running() -> bool:
    try:
        return vdj_query("automix").lower() in {"true", "on", "yes", "1"}
    except Exception:
        return False


def stop_automix_if_running() -> bool:
    was_running = automix_is_running()
    if was_running:
        vdj_execute("automix")
        time.sleep(0.5)
        print("Automix paused for match cue.")
    return was_running


def restore_automix(was_running: bool) -> None:
    stop_all_decks()
    if was_running:
        start_automix_if_needed()


def run_two_song_cue(match: MatchCue) -> None:
    left, right = match.users
    print()
    print(f"Running two-song cue for match {match.match_id}")
    print(f"  A: {left.name}: {left.search_query}")
    print(f"  B: {right.name}: {right.search_query}")

    deck_a = search_and_load_to_deck(left.search_query, deck=1)
    deck_b = search_and_load_to_deck(right.search_query, deck=2)
    set_deck_volume(1, 1.0)
    set_deck_volume(2, 1.0)

    print(f"Loaded A: {deck_a.track.artist} - {deck_a.track.title}")
    print(f"Loaded B: {deck_b.track.artist} - {deck_b.track.title}")

    for _ in range(MAX_SEGMENTS_PER_DECK):
        a_done = deck_is_finished(1)
        b_done = deck_is_finished(2)

        if a_done and b_done:
            print("Both match cue songs are finished.")
            break

        if not a_done:
            play_segment(
                1,
                SEGMENT_SECONDS,
                fade_out=not b_done,
                next_deck=2,
                fade_seconds=FADE_SECONDS,
            )

        b_done = deck_is_finished(2)
        if not b_done:
            a_done = deck_is_finished(1)
            play_segment(
                2,
                SEGMENT_SECONDS,
                fade_out=not a_done,
                next_deck=1,
                fade_seconds=FADE_SECONDS,
            )


def speak_text(text: str) -> None:
    print(f"TTS: {text}")
    if not TTS_ENABLED:
        return

    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "Add-Type -AssemblyName System.Speech; "
            "$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$speaker.Rate = 0; "
            "$speaker.Volume = 100; "
            f"$speaker.Speak({json.dumps(text)});"
        ),
    ]
    subprocess.run(command, check=False)


def run_tts_cue(match: MatchCue) -> None:
    left, right = match.users
    speak_text(f"{left.name} and {right.name}, please come to the hub")


def import_firebase_modules():
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing Firebase Python packages. Install AI_DJ/requirements.txt first."
        ) from exc

    return firebase_admin, credentials, firestore


def initialise_firestore():
    firebase_admin, credentials, firestore = import_firebase_modules()

    if not firebase_admin._apps:
        cred = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
        firebase_admin.initialize_app(cred)

    return firestore.client(), firestore


def build_match_cue(match_id: str, data: dict[str, Any]) -> MatchCue | None:
    users = []
    for user in data.get("users") or []:
        if not isinstance(user, dict):
            continue
        users.append(
            MatchUser(
                profile_id=str(user.get("profileId") or ""),
                name=str(user.get("name") or user.get("nickname") or "Unknown"),
                soundcloud_track=user.get("soundCloudTrack")
                if isinstance(user.get("soundCloudTrack"), dict)
                else None,
            )
        )

    if len(users) < 2:
        return None

    return MatchCue(match_id=match_id, users=(users[0], users[1]))


def queue_match(match: MatchCue) -> None:
    with state_lock:
        if match.match_id in processed_match_ids:
            print(f"Match already processed: {match.match_id}")
            return
        if match.match_id in queued_match_ids:
            print(f"Match already queued: {match.match_id}")
            return

        queued_match_ids.add(match.match_id)
        work_queue.put(match)

    print(f"Queued match cue: {match.match_id}")


def on_matches_snapshot(docs, changes, read_time) -> None:
    del docs, read_time

    for change in changes:
        if change.type.name not in {"ADDED", "MODIFIED"}:
            continue

        data = change.document.to_dict() or {}
        if data.get("status") != MATCH_STATUS_FILTER:
            continue

        match = build_match_cue(change.document.id, data)
        if match is not None:
            queue_match(match)


def start_match_listener(db):
    query = db.collection(MATCHES_COLLECTION).where("status", "==", MATCH_STATUS_FILTER)
    return query.on_snapshot(on_matches_snapshot)


def mark_match_success(db, firestore, match: MatchCue, mode: str) -> None:
    db.collection(MATCHES_COLLECTION).document(match.match_id).set(
        {
            "aiDjCue": {
                "status": "PLAYING",
                "mode": mode,
                "startedAt": firestore.SERVER_TIMESTAMP,
            }
        },
        merge=True,
    )


def mark_match_error(db, firestore, match: MatchCue, error: Exception) -> None:
    db.collection(MATCHES_COLLECTION).document(match.match_id).set(
        {
            "aiDjCue": {
                "status": "ERROR",
                "errorAt": firestore.SERVER_TIMESTAMP,
                "message": str(error),
            }
        },
        merge=True,
    )


def cue_worker(db, firestore) -> None:
    while True:
        match = work_queue.get()
        if match is None:
            work_queue.task_done()
            return

        automix_was_running = False
        try:
            automix_was_running = stop_automix_if_running()

            if match.users[0].has_song and match.users[1].has_song:
                mark_match_success(db, firestore, match, "two_song_crossfade")
                run_two_song_cue(match)
            else:
                mark_match_success(db, firestore, match, "tts_names")
                run_tts_cue(match)

            mark_processed(match.match_id)
        except Exception as exc:
            mark_not_queued(match.match_id)
            print(f"ERROR while running match cue {match.match_id}: {exc}")
            try:
                mark_match_error(db, firestore, match, exc)
            except Exception as firestore_exc:
                print(f"Could not write AIDJ match error: {firestore_exc}")
        finally:
            restore_automix(automix_was_running)
            work_queue.task_done()


def main() -> None:
    print("Cue AIDJ Match Listener")
    print("=" * 32)
    print(f"Matches collection: {MATCHES_COLLECTION}")
    print(f"Match status filter: {MATCH_STATUS_FILTER}")
    print(f"Playlist path: {PLAYLIST_PATH}")
    print(f"Segment/fade: {SEGMENT_SECONDS:g}s / {FADE_SECONDS:g}s")

    load_processed_state()
    print(f"Loaded processed matches: {len(processed_match_ids)}")

    check_virtualdj_connection()
    load_background_playlist()

    db, firestore = initialise_firestore()
    worker = threading.Thread(target=cue_worker, args=(db, firestore), daemon=True)
    worker.start()

    watch = start_match_listener(db)
    print("Listening for matched Cue pairs. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping AIDJ match listener...")
        watch.unsubscribe()
        work_queue.put(None)
        worker.join(timeout=5)


if __name__ == "__main__":
    main()
