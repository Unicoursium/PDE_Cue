from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from os import getenv
from typing import Any
from urllib.parse import urlparse

import requests


# ============================================================
# Configuration
# ============================================================

# Override with VDJ_BASE_URL if your Network Control plugin uses a custom URL,
# for example: http://127.0.0.1:8090
VDJ_BASE_URL = getenv("VDJ_BASE_URL", "").strip()

# Used only when VDJ_BASE_URL is not set. The Network Control plugin is often
# configured on port 80, while this test script originally used 8080.
VDJ_FALLBACK_BASE_URLS = (
    "http://127.0.0.1:8080",
    "http://127.0.0.1:80",
)

# If you configured an authentication string in the
# VirtualDJ Network Control plugin, write it here.
# Otherwise, leave it as an empty string.
VDJ_BEARER_TOKEN = getenv("VDJ_BEARER_TOKEN", "").strip()

# SoundCloud search results may take a few seconds to appear.
SEARCH_TIMEOUT_SECONDS = 12
SEARCH_POLL_INTERVAL_SECONDS = 0.8

_active_vdj_base_url = VDJ_BASE_URL or VDJ_FALLBACK_BASE_URLS[0]


# ============================================================
# Data models
# ============================================================

@dataclass
class SoundCloudTrack:
    url: str
    title: str
    uploader: str

    @property
    def search_query(self) -> str:
        """
        Search using both the uploader and title to reduce the risk
        of selecting the wrong SoundCloud track.
        """
        title = self.title

        if self.uploader:
            lower_title = title.lower()
            lower_uploader = self.uploader.lower()

            for prefix in (f"{lower_uploader} - ", f"{lower_uploader} -"):
                if lower_title.startswith(prefix):
                    title = title[len(prefix):].strip()
                    lower_title = title.lower()
                    break

            suffix = f" by {lower_uploader}"
            if lower_title.endswith(suffix):
                title = title[:-len(suffix)].strip()

        return f"{self.uploader} {title}".strip()


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
# Helper functions
# ============================================================

def vdj_quote(value: str) -> str:
    """
    Escape text for use inside a VDJScript double-quoted string.
    """
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
    """
    Execute a VDJScript command through VirtualDJ Network Control.
    Uses URL query parameters for maximum compatibility.
    """
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
    """
    Query a value from VirtualDJ through Network Control.
    Uses URL query parameters for maximum compatibility.
    """
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


def get_soundcloud_track_metadata(url: str) -> SoundCloudTrack:
    """
    Use SoundCloud's official oEmbed endpoint to read the title and
    uploader of a public SoundCloud URL.

    This does not download audio.
    """
    parsed_url = urlparse(url)

    if parsed_url.netloc.lower() not in {"soundcloud.com", "www.soundcloud.com"}:
        raise RuntimeError(
            "This does not look like a SoundCloud track URL:\n"
            f"{url}"
        )

    try:
        response = requests.get(
            "https://soundcloud.com/oembed",
            params={
                "format": "json",
                "url": url,
            },
            timeout=15,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        response = exc.response
        status = response.status_code if response is not None else "unknown"
        body = response.text if response is not None else str(exc)
        raise RuntimeError(
            "SoundCloud could not read metadata for this URL.\n"
            "Check that it is public and directly points to a playable track.\n"
            f"URL: {url}\n"
            f"HTTP status: {status}\n"
            f"Response: {body}"
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(
            "Could not connect to SoundCloud to read metadata.\n"
            f"URL: {url}\n"
            f"Error: {exc}"
        ) from exc

    payload: dict[str, Any] = response.json()

    title = str(payload.get("title", "")).strip()
    uploader = str(payload.get("author_name", "")).strip()

    if not title:
        raise RuntimeError(
            f"SoundCloud returned no title for this URL:\n{url}"
        )

    return SoundCloudTrack(
        url=url,
        title=title,
        uploader=uploader,
    )


def check_virtualdj_connection() -> None:
    """
    Confirm that VirtualDJ Network Control is reachable.
    """
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
    """
    Read the song currently selected in VirtualDJ's browser list.
    """
    return VirtualDJTrack(
        title=vdj_query("get_browsed_song 'title'"),
        artist=vdj_query("get_browsed_song 'artist'"),
        filepath=vdj_query("get_browsed_filepath"),
    )


def get_indexed_virtualdj_track(index: int) -> VirtualDJTrack:
    """
    Read a song by visible browser row. VirtualDJ search results can expose
    row 0 as a non-track entry, while row 1 is the first playable result.
    """
    return VirtualDJTrack(
        title=vdj_query(f"get_browsed_song {index} 'title'"),
        artist=vdj_query(f"get_browsed_song {index} 'artist'"),
        filepath=vdj_query(f"get_browsed_song {index} 'filepath'"),
    )


def wait_for_search_result() -> VirtualDJTrack:
    """
    Wait until VirtualDJ shows at least one search result.
    """
    deadline = time.time() + SEARCH_TIMEOUT_SECONDS

    while time.time() < deadline:
        try:
            file_count_raw = vdj_query("file_count")
            file_count = int(file_count_raw)
        except (ValueError, requests.RequestException):
            file_count = 0

        if file_count > 0:
            # Select the first playable search result. On some VirtualDJ
            # builds, the top browser row returns error:-2147024891, while
            # scrolling down once selects row 1, the first actual track.
            vdj_execute("browser_window 'songs' & browser_scroll 'top'")
            time.sleep(0.3)

            selected = get_selected_virtualdj_track()

            if not selected.is_valid:
                vdj_execute("browser_scroll +1")
                time.sleep(0.3)
                selected = get_selected_virtualdj_track()

            if selected.is_valid:
                return selected

        time.sleep(SEARCH_POLL_INTERVAL_SECONDS)

    raise TimeoutError(
        "VirtualDJ returned no search result.\n"
        "Confirm that the SoundCloud root folder is selected, "
        "that SoundCloud is logged in, and that the URL points "
        "to a playable public track."
    )


def search_and_add_track(track: SoundCloudTrack) -> VirtualDJTrack:
    """
    Search for a SoundCloud track in VirtualDJ and add the first result
    to the Automix list.
    """
    print()
    print("Searching in VirtualDJ:")
    print(f"  SoundCloud URL: {track.url}")
    print(f"  Search query:   {track.search_query}")

    vdj_execute("clear_search")
    time.sleep(0.3)

    vdj_execute(f"search {vdj_quote(track.search_query)}")

    selected = wait_for_search_result()

    print("  Selected first VirtualDJ result:")
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
    """
    Query the current Automix state first so that we do not accidentally
    toggle an already-running Automix session off.
    """
    current_state = vdj_query("automix").lower()

    if current_state in {"true", "on", "yes", "1"}:
        print("Automix is already running.")
        return

    vdj_execute("automix")
    print("Automix started.")


def main() -> None:
    print("VirtualDJ SoundCloud Automix Test")
    print("=" * 38)

    if len(sys.argv) >= 3:
        url_1 = sys.argv[1].strip()
        url_2 = sys.argv[2].strip()
    else:
        url_1 = input("Paste SoundCloud URL 1: ").strip()
        url_2 = input("Paste SoundCloud URL 2: ").strip()

    if not url_1 or not url_2:
        raise RuntimeError("Two SoundCloud URLs are required.")

    check_virtualdj_connection()

    print()
    print("Reading SoundCloud metadata...")

    track_1 = get_soundcloud_track_metadata(url_1)
    track_2 = get_soundcloud_track_metadata(url_2)

    print(f"Track 1: {track_1.uploader} - {track_1.title}")
    print(f"Track 2: {track_2.uploader} - {track_2.title}")

    # Show the Automix pane and remove any previous tracks.
    vdj_execute("sideview 'automix'")
    vdj_execute("playlist_clear")

    search_and_add_track(track_1)
    search_and_add_track(track_2)

    vdj_execute("clear_search")

    automix_count = get_automix_count()
    print()
    print(f"Tracks currently in Automix: {automix_count}")

    if automix_count != 2:
        raise RuntimeError(
            "The Automix list does not contain exactly two tracks.\n"
            "Check the VirtualDJ search results before continuing."
        )

    start_automix_if_needed()

    print()
    print("Done. VirtualDJ should now begin playing and automatically mix")
    print("from the first SoundCloud track into the second one.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
    except Exception as exc:
        print()
        print("ERROR:")
        print(exc)
        sys.exit(1)
