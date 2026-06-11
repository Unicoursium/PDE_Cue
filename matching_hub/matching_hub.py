import threading
import time
import shutil
import subprocess
import os
import socket
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

from r200_reader import R200Reader, normalize_epc


SERVICE_ACCOUNT_PATH = "serviceAccountKey.json"
POLL_INTERVAL = 0.1
BOLD_AUDIO_REPEAT_SECONDS = 4.0
BOLD_AUDIO_REPEAT_COUNT = 3
BOLD_TTS_AMPLITUDE = os.environ.get("CUE_BOLD_TTS_AMPLITUDE", "200")
BOLD_AUDIO_DEVICE = os.environ.get("CUE_BOLD_AUDIO_DEVICE", "default")
RESET_SOCKET_PATH = Path(
    os.environ.get("CUE_MATCHING_RESET_SOCKET", "/tmp/cue-matching-hub.sock")
)

active_users_by_epc = {}
entered_users_by_epc = {}
matched_pair = None
reset_requested = threading.Event()

state_lock = threading.RLock()


def initialise_firestore():
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)
    return firestore.client()


def gender_matches_looking_for(gender, looking_for):
    gender_to_looking_for = {
        "MAN": "MEN",
        "WOMAN": "WOMEN",
    }

    expected = gender_to_looking_for.get(gender)

    if expected is None:
        return False

    return looking_for == expected


def users_are_compatible(user_a, user_b):
    personality_a = user_a.get("personality")
    personality_b = user_b.get("personality")

    if not personality_a or personality_a != personality_b:
        return False

    a_wants_b = gender_matches_looking_for(
        gender=user_b.get("gender"),
        looking_for=user_a.get("lookingFor"),
    )
    b_wants_a = gender_matches_looking_for(
        gender=user_a.get("gender"),
        looking_for=user_b.get("lookingFor"),
    )

    return a_wants_b and b_wants_a


def normalized_personality(user):
    raw = str(user.get("personality") or "").strip().upper()

    if "BOLD" in raw:
        return "BOLD"
    if "SHY" in raw:
        return "SHY"

    return raw


def find_first_match():
    users = list(entered_users_by_epc.values())

    for i, user_a in enumerate(users):
        for user_b in users[i + 1 :]:
            if users_are_compatible(user_a, user_b):
                return user_a, user_b

    return None


def clear_match_state():
    global matched_pair

    with state_lock:
        entered_users_by_epc.clear()
        matched_pair = None

    reset_requested.clear()
    print("Matching hub state reset. Returning to R200 scanning.")


def request_match_reset():
    reset_requested.set()
    print("Matching hub reset requested.")


def reset_socket_loop():
    RESET_SOCKET_PATH.unlink(missing_ok=True)

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(RESET_SOCKET_PATH))
        os.chmod(RESET_SOCKET_PATH, 0o666)
        server.listen(1)
        print(f"Listening for reset commands on {RESET_SOCKET_PATH}")

        while True:
            connection, _ = server.accept()
            with connection:
                command = connection.recv(64).decode(errors="replace").strip().upper()

                if command == "RESET":
                    request_match_reset()
                    connection.sendall(b"OK\n")
                else:
                    connection.sendall(b"UNKNOWN\n")


def on_profiles_snapshot(docs, changes, read_time):
    del docs, read_time

    with state_lock:
        for change in changes:
            data = change.document.to_dict() or {}
            rfid_epc = data.get("rfidEpc")
            status = data.get("status")

            if not rfid_epc:
                continue

            rfid_epc = normalize_epc(rfid_epc)

            if change.type.name in ("ADDED", "MODIFIED") and status == "ACTIVE":
                active_users_by_epc[rfid_epc] = {
                    "userId": data.get("userId"),
                    "name": data.get("name"),
                    "age": data.get("age"),
                    "gender": data.get("gender"),
                    "lookingFor": data.get("lookingFor"),
                    "personality": data.get("personality"),
                    "rfidEpc": rfid_epc,
                }

                print(
                    "ACTIVE USER:",
                    data.get("name"),
                    "/",
                    rfid_epc,
                    "/",
                    data.get("gender"),
                    "->",
                    data.get("lookingFor"),
                    "/",
                    data.get("personality"),
                )

            else:
                active_users_by_epc.pop(rfid_epc, None)
                print(f"INACTIVE USER REMOVED FROM ACTIVE CACHE: {rfid_epc}")

        print(f"Active cloud users: {len(active_users_by_epc)}")


def start_firestore_listener(db):
    query = db.collection("profiles").where("status", "==", "ACTIVE")
    return query.on_snapshot(on_profiles_snapshot)


def note_entered_range(tag):
    epc = normalize_epc(tag["epc"])

    with state_lock:
        user = active_users_by_epc.get(epc)

        if not user:
            return None

        if epc in entered_users_by_epc:
            return None

        entered_users_by_epc[epc] = {
            **user,
            "firstSeen": time.time(),
            "firstRssi": tag.get("rssi"),
        }

        print(
            f"ENTERED BAR RANGE: {user['name']} / "
            f"{epc} / RSSI {tag.get('rssi')} dBm"
        )

        return entered_users_by_epc[epc]


def maybe_create_match():
    global matched_pair

    with state_lock:
        if matched_pair is not None:
            return matched_pair

        pair = find_first_match()

        if pair is None:
            return None

        matched_pair = pair
        user_a, user_b = matched_pair

        print()
        print("MATCH FOUND")
        print(
            f"{user_a['name']} <-> {user_b['name']} "
            f"/ {user_a['personality']}"
        )
        print(f"EPC A: {user_a['rfidEpc']}")
        print(f"EPC B: {user_b['rfidEpc']}")
        print()

        return matched_pair


def speak_text(text):
    if shutil.which("espeak-ng") and shutil.which("aplay"):
        espeak = subprocess.Popen(
            [
                "espeak-ng",
                "--stdout",
                "-s",
                "145",
                "-a",
                BOLD_TTS_AMPLITUDE,
                text,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        aplay = subprocess.run(
            ["aplay", "-D", BOLD_AUDIO_DEVICE, "-q"],
            stdin=espeak.stdout,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        if espeak.stdout:
            espeak.stdout.close()

        _, espeak_error = espeak.communicate()

        if espeak.returncode != 0:
            print(f"espeak-ng failed: {espeak_error.decode(errors='replace')}")
        if aplay.returncode != 0:
            print(f"aplay failed: {aplay.stderr}")
        return

    if shutil.which("espeak-ng"):
        result = subprocess.run(
            ["espeak-ng", "-s", "145", "-a", BOLD_TTS_AMPLITUDE, text],
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(f"espeak-ng failed: {result.stderr}")
        return

    if shutil.which("spd-say"):
        subprocess.run(["spd-say", text], check=False)
        return

    print("No text-to-speech command found. Install espeak-ng.")


def run_shy_match_alert(reader, user_a, user_b):
    selected_epcs = [
        user_a["rfidEpc"],
        user_b["rfidEpc"],
    ]

    reader.initialise()
    print("SHY match: alternating matched tag LED alerts...")

    while not reset_requested.is_set():
        try:
            for epc in selected_epcs:
                if reset_requested.is_set():
                    break
                reader.select_epc_and_trigger_led(epc)
                time.sleep(0.15)

        except Exception as error:
            print(f"Selected tag LED loop error: {error}")
            time.sleep(1)


def run_bold_match_alert(user_a, user_b):
    name_a = user_a.get("name") or "left player"
    name_b = user_b.get("name") or "right player"
    message = f"{name_a} and {name_b}, you are matched, please come to the hub."

    print("BOLD match: announcing names through speaker...")
    print(f"Announcement: {message}")

    for _ in range(BOLD_AUDIO_REPEAT_COUNT):
        if reset_requested.is_set():
            break
        speak_text(message)
        time.sleep(BOLD_AUDIO_REPEAT_SECONDS)

    print("BOLD match announcement completed. Waiting for kiosk reset...")

    while not reset_requested.is_set():
        time.sleep(0.2)


def run_match_alert(reader, user_a, user_b):
    personality = normalized_personality(user_a)

    if personality == "SHY":
        run_shy_match_alert(reader, user_a, user_b)
        return

    if personality == "BOLD":
        run_bold_match_alert(user_a, user_b)
        return

    print(f"Unknown personality '{personality}'. No match alert configured.")


def r200_loop():
    reader = R200Reader()
    reader.connect()

    while True:
        clear_match_state()
        reader.initialise()

        print("R200 scanning all tags...")

        pair = None
        while pair is None:
            try:
                tags = reader.inventory_once()

                for tag in tags:
                    note_entered_range(tag)

                pair = maybe_create_match()

                if pair is None:
                    time.sleep(POLL_INTERVAL)

            except Exception as error:
                print(f"R200 scan loop error: {error}")
                time.sleep(1)

        user_a, user_b = pair
        run_match_alert(reader, user_a, user_b)


def main():
    print("Cue matching hub starting...")

    db = initialise_firestore()
    watch = start_firestore_listener(db)
    print("Listening for ACTIVE profiles...")

    reset_thread = threading.Thread(target=reset_socket_loop, daemon=True)
    reset_thread.start()

    r200_thread = threading.Thread(target=r200_loop, daemon=True)
    r200_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
        watch.unsubscribe()


if __name__ == "__main__":
    main()
