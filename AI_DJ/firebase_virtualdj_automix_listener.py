from __future__ import annotations

import json
import queue
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from os import getenv
from pathlib import Path
from typing import Any
from difflib import SequenceMatcher
from urllib.parse import urlparse

import requests


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and getenv(key) is None:
            import os

            os.environ[key] = value


# ============================================================
# Configuration
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = SCRIPT_DIR.parent

load_dotenv(SCRIPT_DIR / ".env")

SERVICE_ACCOUNT_PATH = Path(
    getenv("FIREBASE_SERVICE_ACCOUNT", "")
    or getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    or SCRIPT_DIR / "serviceAccountKey.json"
)

if not SERVICE_ACCOUNT_PATH.exists():
    fallback_service_account = WORKSPACE_DIR / "matching_hub" / "serviceAccountKey.json"
    if fallback_service_account.exists():
        SERVICE_ACCOUNT_PATH = fallback_service_account

PROFILES_COLLECTION = getenv("AIDJ_PROFILES_COLLECTION", "profiles")
PROFILE_STATUS_FILTER = getenv("AIDJ_PROFILE_STATUS", "ONBOARDING_SUBMITTED")
TRACK_FIELD = getenv("AIDJ_TRACK_FIELD", "soundCloudTrack")

STATE_PATH = Path(
    getenv("AIDJ_STATE_PATH", str(SCRIPT_DIR / "processed_soundcloud_tracks.json"))
)

# By default, the formal listener appends to the existing Automix list.
CLEAR_AUTOMIX_ON_START = getenv("AIDJ_CLEAR_AUTOMIX_ON_START", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# Starting playback is intentionally opt-in; this script's default job is to
# keep VirtualDJ's Automix list up to date.
START_AUTOMIX_AFTER_ADD = getenv("AIDJ_START_AUTOMIX", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

VDJ_BASE_URL = getenv("VDJ_BASE_URL", "").strip()
VDJ_FALLBACK_BASE_URLS = (
    "http://127.0.0.1:8080",
    "http://127.0.0.1:80",
)
VDJ_BEARER_TOKEN = getenv("VDJ_BEARER_TOKEN", "").strip()

SEARCH_TIMEOUT_SECONDS = float(getenv("AIDJ_SEARCH_TIMEOUT_SECONDS", "15"))
SEARCH_POLL_INTERVAL_SECONDS = float(getenv("AIDJ_SEARCH_POLL_INTERVAL_SECONDS", "0.8"))

_active_vdj_base_url = VDJ_BASE_URL or VDJ_FALLBACK_BASE_URLS[0]


# ============================================================
# Data models
# ============================================================

@dataclass(frozen=True)
class FirebaseTrack:
    profile_id: str
    url: str
    title: str
    artists: str
    soundcloud_id: str
    updated_at: Any

    @property
    def dedupe_key(self) -> str:
        if self.soundcloud_id:
            return f"profile:{self.profile_id}:soundcloud:{self.soundcloud_id}"

        return f"profile:{self.profile_id}:url:{normalise_soundcloud_url(self.url)}"

    @property
    def search_query(self) -> str:
        title = clean_track_title(self.title, self.artists)
        return f"{self.artists} {title}".strip() or self.url


@dataclass
class VirtualDJTrack:
    title: str
    artist: str
    filepath: str

    @property
    def is_valid(self) -> bool:
        values = (self.title, self.artist, self.filepath)
        return any(values) and not any(value.lower().startswith("error:") for value in values)


# ============================================================
# State
# ============================================================

state_lock = threading.RLock()
work_queue: queue.Queue[FirebaseTrack | None] = queue.Queue()
queued_keys: set[str] = set()
processed_keys: set[str] = set()


# ============================================================
# Utility functions
# ============================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_track_title(title: str, artists: str) -> str:
    title = (title or "").strip()
    artists = (artists or "").strip()

    if not artists:
        return title

    lower_title = title.lower()
    lower_artists = artists.lower()

    for prefix in (f"{lower_artists} - ", f"{lower_artists} -"):
        if lower_title.startswith(prefix):
            title = title[len(prefix):].strip()
            lower_title = title.lower()
            break

    suffix = f" by {lower_artists}"
    if lower_title.endswith(suffix):
        title = title[:-len(suffix)].strip()

    return title


def normalise_soundcloud_url(url: str) -> str:
    parsed = urlparse((url or "").strip())

    if not parsed.scheme or not parsed.netloc:
        return url.strip()

    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def normalise_match_text(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def text_similarity(left: str, right: str) -> float:
    left_normalised = normalise_match_text(left)
    right_normalised = normalise_match_text(right)

    if not left_normalised or not right_normalised:
        return 0.0

    return SequenceMatcher(None, left_normalised, right_normalised).ratio()


def is_soundcloud_url(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    return parsed.netloc.lower() in {"soundcloud.com", "www.soundcloud.com"}


def load_processed_state() -> None:
    if not STATE_PATH.exists():
        return

    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read state file {STATE_PATH}: {exc}")
        return

    keys = payload.get("processedKeys", [])

    if isinstance(keys, list):
        processed_keys.update(str(key) for key in keys)


def save_processed_state() -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updatedAt": utc_now_iso(),
        "processedKeys": sorted(processed_keys),
    }
    STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def mark_processed(track: FirebaseTrack) -> None:
    with state_lock:
        processed_keys.add(track.dedupe_key)
        queued_keys.discard(track.dedupe_key)
        save_processed_state()


def mark_not_queued(track: FirebaseTrack) -> None:
    with state_lock:
        queued_keys.discard(track.dedupe_key)


# ============================================================
# VirtualDJ Network Control
# ============================================================

def vdj_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def get_vdj_headers() -> dict[str, str]:
    if not VDJ_BEARER_TOKEN:
        return {}

    return {
        "Authorization": f"Bearer {VDJ_BEARER_TOKEN}",
    }


def set_active_vdj_base_url(base_url: str) -> None:
    global _active_vdj_base_url
    _active_vdj_base_url = base_url.rstrip("/")


def candidate_vdj_base_urls() -> list[str]:
    if VDJ_BASE_URL:
        return [VDJ_BASE_URL.rstrip("/")]

    return list(VDJ_FALLBACK_BASE_URLS)


def vdj_execute(script: str) -> str:
    params = {"script": script}

    if VDJ_BEARER_TOKEN:
        params["bearer"] = VDJ_BEARER_TOKEN

    response = requests.get(
        f"{_active_vdj_base_url}/execute",
        params=params,
        headers=get_vdj_headers(),
        timeout=10,
    )

    if not response.ok:
        raise RuntimeError(
            "VirtualDJ rejected an execute request.\n"
            f"HTTP status: {response.status_code}\n"
            f"Request URL: {response.url}\n"
            f"Response: {response.text}"
        )

    return response.text.strip()


def vdj_query(script: str) -> str:
    params = {"script": script}

    if VDJ_BEARER_TOKEN:
        params["bearer"] = VDJ_BEARER_TOKEN

    response = requests.get(
        f"{_active_vdj_base_url}/query",
        params=params,
        headers=get_vdj_headers(),
        timeout=10,
    )

    if not response.ok:
        raise RuntimeError(
            "VirtualDJ rejected a query request.\n"
            f"HTTP status: {response.status_code}\n"
            f"Request URL: {response.url}\n"
            f"Response: {response.text}"
        )

    return response.text.strip()


def check_virtualdj_connection() -> None:
    errors: list[str] = []

    for base_url in candidate_vdj_base_urls():
        set_active_vdj_base_url(base_url)

        try:
            clock = vdj_query("get_clock")
        except (RuntimeError, requests.RequestException) as exc:
            errors.append(f"{base_url}: {exc}")
            continue

        print(f"Connected to VirtualDJ at {base_url}. Current VirtualDJ clock: {clock}")
        return

    raise RuntimeError(
        "Could not connect to VirtualDJ Network Control.\n"
        "Check that VirtualDJ is running, Network Control is enabled, "
        "and the configured port is correct.\n"
        "Tried:\n"
        + "\n".join(f"  - {error}" for error in errors)
    )


def get_selected_virtualdj_track() -> VirtualDJTrack:
    return VirtualDJTrack(
        title=vdj_query("get_browsed_song 'title'"),
        artist=vdj_query("get_browsed_song 'artist'"),
        filepath=vdj_query("get_browsed_filepath"),
    )


def get_indexed_virtualdj_track(index: int) -> VirtualDJTrack:
    return VirtualDJTrack(
        title=vdj_query(f"get_browsed_song {index} 'title'"),
        artist=vdj_query(f"get_browsed_song {index} 'artist'"),
        filepath=vdj_query(f"get_browsed_song {index} 'filepath'"),
    )


def select_virtualdj_browser_row(index: int) -> VirtualDJTrack:
    vdj_execute("browser_window 'songs' & browser_scroll 'top'")
    time.sleep(0.2)
    vdj_execute(f"browser_scroll +{index}")
    time.sleep(0.3)
    return get_selected_virtualdj_track()


def virtualdj_track_matches_target(candidate: VirtualDJTrack, target: FirebaseTrack) -> bool:
    if not candidate.is_valid:
        return False

    if target.soundcloud_id and candidate.filepath.lower() == f"netsearch://sc{target.soundcloud_id}".lower():
        return True

    title = clean_track_title(target.title, target.artists)
    title_score = text_similarity(candidate.title, title)
    artist_score = text_similarity(candidate.artist, target.artists)

    return title_score >= 0.92 and (not target.artists or artist_score >= 0.75)


def find_matching_search_result(target: FirebaseTrack) -> tuple[int, VirtualDJTrack] | None:
    try:
        file_count_raw = vdj_query("file_count")
        file_count = int(file_count_raw)
    except (ValueError, RuntimeError, requests.RequestException):
        return None

    if file_count <= 0:
        return None

    max_rows_to_scan = min(file_count, 40)
    vdj_execute("browser_window 'songs' & browser_scroll 'top'")
    time.sleep(0.2)

    for index in range(1, max_rows_to_scan + 1):
        try:
            vdj_execute("browser_scroll +1")
            time.sleep(0.15)
            candidate = get_selected_virtualdj_track()
        except (RuntimeError, requests.RequestException):
            continue

        if virtualdj_track_matches_target(candidate, target):
            return index, candidate

    return None


def wait_for_search_result(target: FirebaseTrack) -> VirtualDJTrack:
    deadline = time.time() + SEARCH_TIMEOUT_SECONDS

    while time.time() < deadline:
        matched = find_matching_search_result(target)

        if matched is not None:
            index, _ = matched
            selected = select_virtualdj_browser_row(index)

            if virtualdj_track_matches_target(selected, target):
                return selected

        time.sleep(SEARCH_POLL_INTERVAL_SECONDS)

    raise TimeoutError(
        "VirtualDJ returned search results, but none matched the requested "
        "SoundCloud track closely enough.\n"
        f"Requested ID: {target.soundcloud_id or 'unknown'}\n"
        f"Requested title: {target.title}\n"
        f"Requested artist: {target.artists}\n"
        "This protects Automix from adding the wrong song."
    )


def add_track_to_automix(track: FirebaseTrack) -> VirtualDJTrack:
    print()
    print(f"Adding profile {track.profile_id} to VirtualDJ Automix")
    print(f"  URL:    {track.url}")
    print(f"  ID:     {track.soundcloud_id or 'unknown'}")
    print(f"  Search: {track.search_query}")

    vdj_execute("clear_search")
    time.sleep(0.3)
    vdj_execute(f"search {vdj_quote(track.search_query)}")

    selected = wait_for_search_result(track)

    print("  Selected VirtualDJ result:")
    print(f"    Artist: {selected.artist}")
    print(f"    Title:  {selected.title}")
    print(f"    Path:   {selected.filepath}")

    vdj_execute("playlist_add")
    return selected


def get_automix_count() -> int:
    raw_value = vdj_query("file_count automix")

    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            f"VirtualDJ returned an unexpected Automix count: {raw_value!r}"
        ) from exc


def start_automix_if_needed() -> None:
    current_state = vdj_query("automix").lower()

    if current_state in {"true", "on", "yes", "1"}:
        print("Automix is already running.")
        return

    vdj_execute("automix")
    print("Automix started.")


# ============================================================
# Firestore
# ============================================================

def import_firebase_modules():
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing Firebase Python packages.\n"
            "Install them with:\n"
            "  python -m pip install -r C:\\PDE_Files\\AI_DJ\\requirements.txt"
        ) from exc

    return firebase_admin, credentials, firestore


def initialise_firestore():
    if not SERVICE_ACCOUNT_PATH.exists():
        raise RuntimeError(
            "Firebase service account JSON was not found.\n"
            f"Expected: {SERVICE_ACCOUNT_PATH}\n"
            "Set FIREBASE_SERVICE_ACCOUNT to the JSON path, or place "
            "serviceAccountKey.json in C:\\PDE_Files\\AI_DJ."
        )

    firebase_admin, credentials, firestore = import_firebase_modules()

    if not firebase_admin._apps:
        cred = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
        firebase_admin.initialize_app(cred)

    return firestore.client(), firestore


def extract_track_from_profile(profile_id: str, data: dict[str, Any]) -> FirebaseTrack | None:
    track_data = data.get(TRACK_FIELD)

    if not isinstance(track_data, dict):
        return None

    url = str(track_data.get("url") or "").strip()

    if not url or not is_soundcloud_url(url):
        return None

    return FirebaseTrack(
        profile_id=profile_id,
        url=url,
        title=str(track_data.get("title") or "").strip(),
        artists=str(track_data.get("artists") or "").strip(),
        soundcloud_id=str(track_data.get("id") or "").strip(),
        updated_at=data.get("updatedAt"),
    )


def already_marked_added(data: dict[str, Any]) -> bool:
    ai_dj = data.get("aiDjAutomix")
    return isinstance(ai_dj, dict) and ai_dj.get("status") == "ADDED_TO_AUTOMIX"


def queue_track(track: FirebaseTrack) -> None:
    with state_lock:
        if track.dedupe_key in processed_keys:
            print(f"Already processed profile {track.profile_id}: {track.search_query}")
            return

        if track.dedupe_key in queued_keys:
            print(f"Already queued profile {track.profile_id}: {track.search_query}")
            return

        queued_keys.add(track.dedupe_key)
        work_queue.put(track)

    print(f"Queued SoundCloud track from profile {track.profile_id}: {track.search_query}")


def on_profiles_snapshot(docs, changes, read_time) -> None:
    del docs, read_time

    for change in changes:
        if change.type.name not in {"ADDED", "MODIFIED"}:
            continue

        data = change.document.to_dict() or {}

        if data.get("status") != PROFILE_STATUS_FILTER:
            continue

        if already_marked_added(data):
            continue

        track = extract_track_from_profile(change.document.id, data)

        if track is None:
            continue

        queue_track(track)


def start_firestore_listener(db):
    query = db.collection(PROFILES_COLLECTION).where("status", "==", PROFILE_STATUS_FILTER)
    return query.on_snapshot(on_profiles_snapshot)


def mark_firestore_success(db, firestore, track: FirebaseTrack, selected: VirtualDJTrack) -> None:
    doc_ref = db.collection(PROFILES_COLLECTION).document(track.profile_id)
    doc_ref.set(
        {
            "aiDjAutomix": {
                "status": "ADDED_TO_AUTOMIX",
                "addedAt": firestore.SERVER_TIMESTAMP,
                "dedupeKey": track.dedupe_key,
                "virtualDj": {
                    "artist": selected.artist,
                    "title": selected.title,
                    "filepath": selected.filepath,
                },
            }
        },
        merge=True,
    )


def mark_firestore_error(db, firestore, track: FirebaseTrack, error: Exception) -> None:
    doc_ref = db.collection(PROFILES_COLLECTION).document(track.profile_id)
    doc_ref.set(
        {
            "aiDjAutomix": {
                "status": "ERROR",
                "errorAt": firestore.SERVER_TIMESTAMP,
                "dedupeKey": track.dedupe_key,
                "message": str(error),
            }
        },
        merge=True,
    )


# ============================================================
# Worker
# ============================================================

def automix_worker(db, firestore) -> None:
    while True:
        track = work_queue.get()

        if track is None:
            work_queue.task_done()
            return

        try:
            selected = add_track_to_automix(track)
            automix_count = get_automix_count()
            print(f"Automix count: {automix_count}")

            if START_AUTOMIX_AFTER_ADD:
                start_automix_if_needed()

            mark_processed(track)
            mark_firestore_success(db, firestore, track, selected)
        except Exception as exc:
            mark_not_queued(track)
            print()
            print(f"ERROR while adding profile {track.profile_id}:")
            print(exc)

            try:
                mark_firestore_error(db, firestore, track, exc)
            except Exception as firestore_exc:
                print(f"Could not write error status to Firestore: {firestore_exc}")
        finally:
            work_queue.task_done()


# ============================================================
# Main
# ============================================================

def main() -> None:
    print("Firebase -> VirtualDJ Automix Listener")
    print("=" * 40)
    print(f"Firestore collection: {PROFILES_COLLECTION}")
    print(f"Profile status filter: {PROFILE_STATUS_FILTER}")
    print(f"Track field: {TRACK_FIELD}")
    print(f"State file: {STATE_PATH}")

    load_processed_state()
    print(f"Loaded processed track keys: {len(processed_keys)}")

    check_virtualdj_connection()

    if CLEAR_AUTOMIX_ON_START:
        vdj_execute("sideview 'automix'")
        vdj_execute("playlist_clear")
        print("Cleared VirtualDJ Automix list.")

    db, firestore = initialise_firestore()
    worker = threading.Thread(target=automix_worker, args=(db, firestore), daemon=True)
    worker.start()

    watch = start_firestore_listener(db)
    print("Listening for Firestore profile changes. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping listener...")
        watch.unsubscribe()
        work_queue.put(None)
        worker.join(timeout=10)
        print("Stopped.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print("ERROR:")
        print(exc)
        sys.exit(1)
