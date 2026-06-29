from __future__ import annotations

import hashlib
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

import requests

from aidj_two_deck_16s_demo import (
    deck_is_finished,
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
STORAGE_BUCKET = getenv("AIDJ_STORAGE_BUCKET", "pde-g18-test.firebasestorage.app")
SEGMENT_SECONDS = float(getenv("AIDJ_MATCH_SEGMENT_SECONDS", "8"))
FADE_SECONDS = float(getenv("AIDJ_MATCH_FADE_SECONDS", "2"))
AB_REPEATS = int(getenv("AIDJ_MATCH_AB_REPEATS", "2"))
TTS_ENABLED = getenv("AIDJ_TTS_ENABLED", "1").lower() in {"1", "true", "yes", "on"}
PRONUNCIATION_ENABLED = getenv("AIDJ_PRONUNCIATION_ENABLED", "1").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
PRONUNCIATION_CACHE_DIR = Path(
    getenv("AIDJ_PRONUNCIATION_CACHE", str(SCRIPT_DIR / ".pronunciation_cache"))
)
STOP_ON_KIOSK_SCAN = getenv("AIDJ_STOP_ON_KIOSK_SCAN", "1").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
KIOSK_STOP_STATUSES = {"WRISTBANDS_SCANNED", "GAME_STARTED", "PLAYING"}


@dataclass(frozen=True)
class MatchUser:
    profile_id: str
    name: str
    soundcloud_track: dict[str, Any] | None
    pronunciation: dict[str, Any] | None

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


def match_should_stop_for_kiosk(db, match_id: str) -> bool:
    if not STOP_ON_KIOSK_SCAN:
        return False

    try:
        snapshot = db.collection(MATCHES_COLLECTION).document(match_id).get()
    except Exception as exc:
        print(f"Could not check kiosk status for match {match_id}: {exc}")
        return False

    if not snapshot.exists:
        return False

    data = snapshot.to_dict() or {}
    kiosk = data.get("kiosk")
    if not isinstance(kiosk, dict):
        return False

    status = str(kiosk.get("status") or "").strip().upper()
    return status in KIOSK_STOP_STATUSES


def wait_with_kiosk_stop(db, match_id: str, seconds: float) -> bool:
    started_at = time.monotonic()
    while time.monotonic() - started_at < seconds:
        if match_should_stop_for_kiosk(db, match_id):
            print(f"Kiosk started for match {match_id}; stopping AIDJ cue.")
            return True
        time.sleep(0.25)

    return False


def crossfade_with_kiosk_stop(db, match_id: str, from_deck: int, to_deck: int, seconds: float) -> bool:
    print(f"Crossfading deck {from_deck} -> deck {to_deck} over {seconds:g}s")
    set_deck_volume(to_deck, 0.0)
    vdj_execute(f"deck {to_deck} play")

    steps = 20
    delay = seconds / steps if seconds > 0 else 0

    for step in range(steps + 1):
        if match_should_stop_for_kiosk(db, match_id):
            print(f"Kiosk started for match {match_id}; stopping AIDJ cue.")
            stop_all_decks()
            return True

        amount = step / steps
        set_deck_volume(from_deck, 1.0 - amount)
        set_deck_volume(to_deck, amount)
        if delay:
            time.sleep(delay)

    vdj_execute(f"deck {from_deck} pause")
    set_deck_volume(from_deck, 1.0)
    set_deck_volume(to_deck, 1.0)
    time.sleep(0.1)
    return False


def play_segment_with_kiosk_stop(
    db,
    match_id: str,
    deck: int,
    seconds: float,
    fade_out=False,
    next_deck=None,
    fade_seconds=0.0,
) -> bool:
    print(f"Playing deck {deck} for {seconds:g}s")
    set_deck_volume(deck, 1.0)
    vdj_execute(f"deck {deck} play")

    hold_seconds = max(0.0, seconds - (fade_seconds if fade_out and next_deck else 0.0))

    started_at = time.monotonic()
    while time.monotonic() - started_at < hold_seconds:
        if match_should_stop_for_kiosk(db, match_id):
            print(f"Kiosk started for match {match_id}; stopping AIDJ cue.")
            stop_all_decks()
            return True
        if deck_is_finished(deck):
            print(f"Deck {deck} appears to be finished.")
            vdj_execute(f"deck {deck} pause")
            return False
        time.sleep(0.25)

    if fade_out and next_deck is not None:
        return crossfade_with_kiosk_stop(db, match_id, deck, next_deck, fade_seconds)

    vdj_execute(f"deck {deck} pause")
    time.sleep(0.25)
    return False


def run_two_song_cue(db, match: MatchCue) -> bool:
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

    sequence = [1, 2] * AB_REPEATS
    print(
        "Playing fixed match cue sequence: "
        + " ".join("A" if deck == 1 else "B" for deck in sequence)
        + f" ({SEGMENT_SECONDS:g}s each)"
    )

    for index, deck in enumerate(sequence):
        if deck_is_finished(deck):
            print(f"Deck {deck} appears to be finished before segment {index + 1}.")
            continue

        next_deck = sequence[index + 1] if index + 1 < len(sequence) else None
        if play_segment_with_kiosk_stop(
            db,
            match.match_id,
            deck,
            SEGMENT_SECONDS,
            fade_out=next_deck is not None and FADE_SECONDS > 0,
            next_deck=next_deck,
            fade_seconds=FADE_SECONDS,
        ):
            return True

    stop_all_decks()
    print("Fixed match cue sequence complete.")

    return False


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


def pronunciation_download_url(user: MatchUser) -> str | None:
    if not isinstance(user.pronunciation, dict):
        return None

    url = str(user.pronunciation.get("downloadUrl") or "").strip()
    return url or None


def pronunciation_storage_path(user: MatchUser) -> str | None:
    if not isinstance(user.pronunciation, dict):
        return None

    storage_path = str(user.pronunciation.get("storagePath") or "").strip()
    return storage_path or None


def pronunciation_cache_path(user: MatchUser, source_key: str) -> Path:
    file_name = ""
    if isinstance(user.pronunciation, dict):
        file_name = str(user.pronunciation.get("fileName") or "").strip()

    suffix = Path(file_name).suffix or ".m4a"
    digest = hashlib.sha1(source_key.encode("utf-8")).hexdigest()
    profile_part = "".join(
        char for char in (user.profile_id or user.name or "profile") if char.isalnum()
    )
    profile_part = profile_part[:24] or "profile"
    return PRONUNCIATION_CACHE_DIR / f"{profile_part}_{digest[:12]}{suffix}"


def download_pronunciation(user: MatchUser) -> Path | None:
    url = pronunciation_download_url(user)
    storage_path = pronunciation_storage_path(user)
    if not url and not storage_path:
        return None

    PRONUNCIATION_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    source_key = url or f"gs://{STORAGE_BUCKET}/{storage_path}"
    cache_path = pronunciation_cache_path(user, source_key)
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path

    if url:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        cache_path.write_bytes(response.content)
    else:
        from firebase_admin import storage

        blob = storage.bucket(STORAGE_BUCKET).blob(storage_path)
        blob.download_to_filename(str(cache_path))

    return cache_path


def play_audio_file(path: Path) -> None:
    # Windows MediaPlayer can handle the Android .m4a/AAC recordings.
    ps_path = json.dumps(str(path.resolve()))
    script = (
        "Add-Type -AssemblyName PresentationCore; "
        f"$path = {ps_path}; "
        "$player = New-Object System.Windows.Media.MediaPlayer; "
        "$player.Open([uri]$path); "
        "Start-Sleep -Milliseconds 250; "
        "$player.Play(); "
        "$limit = (Get-Date).AddSeconds(10); "
        "while (-not $player.NaturalDuration.HasTimeSpan -and (Get-Date) -lt $limit) { "
        "Start-Sleep -Milliseconds 100 "
        "} "
        "if ($player.NaturalDuration.HasTimeSpan) { "
        "$duration = [int]$player.NaturalDuration.TimeSpan.TotalMilliseconds + 250; "
        "Start-Sleep -Milliseconds $duration "
        "} else { "
        "Start-Sleep -Milliseconds 1500 "
        "} "
        "$player.Stop(); "
        "$player.Close();"
    )
    subprocess.run(
        ["powershell", "-STA", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True,
    )


def play_pronunciation(user: MatchUser) -> bool:
    if not PRONUNCIATION_ENABLED:
        return False

    try:
        path = download_pronunciation(user)
        if path is None:
            return False

        print(f"Playing pronunciation for {user.name}: {path}")
        play_audio_file(path)
        return True
    except Exception as exc:
        print(f"Could not use pronunciation for {user.name}; falling back to TTS: {exc}")
        return False


def run_tts_cue(match: MatchCue) -> None:
    left, right = match.users
    left_recorded = play_pronunciation(left)

    if left_recorded:
        speak_text("and")
    else:
        speak_text(f"{left.name} and")

    if play_pronunciation(right):
        speak_text("please come to the hub")
        return

    speak_text(f"{right.name}, please come to the hub")



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
        firebase_admin.initialize_app(cred, {"storageBucket": STORAGE_BUCKET})

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
                pronunciation=user.get("pronunciation")
                if isinstance(user.get("pronunciation"), dict)
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


def mark_match_stopped_by_kiosk(db, firestore, match: MatchCue) -> None:
    db.collection(MATCHES_COLLECTION).document(match.match_id).set(
        {
            "aiDjCue": {
                "status": "STOPPED_BY_KIOSK",
                "stoppedAt": firestore.SERVER_TIMESTAMP,
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
        stopped_by_kiosk = False
        try:
            automix_was_running = stop_automix_if_running()

            if match.users[0].has_song and match.users[1].has_song:
                mark_match_success(db, firestore, match, "two_song_crossfade")
                stopped_by_kiosk = run_two_song_cue(db, match)
            else:
                mark_match_success(db, firestore, match, "tts_names")
                run_tts_cue(match)
                stopped_by_kiosk = match_should_stop_for_kiosk(db, match.match_id)

            if stopped_by_kiosk:
                mark_match_stopped_by_kiosk(db, firestore, match)
            mark_processed(match.match_id)
        except Exception as exc:
            mark_not_queued(match.match_id)
            print(f"ERROR while running match cue {match.match_id}: {exc}")
            try:
                mark_match_error(db, firestore, match, exc)
            except Exception as firestore_exc:
                print(f"Could not write AIDJ match error: {firestore_exc}")
        finally:
            if stopped_by_kiosk:
                stop_all_decks()
                print("AIDJ cue stopped because kiosk started; Automix remains paused.")
            else:
                restore_automix(automix_was_running)
            work_queue.task_done()


def main() -> None:
    print("Cue AIDJ Match Listener")
    print("=" * 32)
    print(f"Matches collection: {MATCHES_COLLECTION}")
    print(f"Match status filter: {MATCH_STATUS_FILTER}")
    print(f"Storage bucket: {STORAGE_BUCKET}")
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
