import threading
import time
import os
import socket
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

from r200_reader import R200Reader, normalize_epc


SERVICE_ACCOUNT_PATH = "serviceAccountKey.json"
POLL_INTERVAL = 0.1
PROFILE_READY_STATUS = os.environ.get("CUE_PROFILE_READY_STATUS", "WRISTBAND_SCANNED")
PROFILE_MATCHED_STATUS = os.environ.get("CUE_PROFILE_MATCHED_STATUS", "MATCHED")
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


def normalize_gender(value):
    raw = str(value or "").strip().upper()

    if raw in ("MAN", "MALE", "M"):
        return "MAN"
    if raw in ("WOMAN", "WOMEN", "FEMALE", "F"):
        return "WOMAN"
    if raw:
        return "OTHER"

    return None


def normalize_orientation(value):
    raw = str(value or "").strip().upper()
    compact = raw.replace(" ", "").replace("-", "").replace("_", "")

    if compact in ("HETEROSEXUAL", "STRAIGHT"):
        return "HETEROSEXUAL"
    if compact in ("HOMOSEXUAL", "GAY", "LESBIAN"):
        return "HOMOSEXUAL"
    if compact in ("BISEXUAL", "BI"):
        return "BISEXUAL"
    if compact in ("PANSEXUAL", "PAN"):
        return "PANSEXUAL"

    return None


def parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_age_range(value):
    if not isinstance(value, dict):
        return None, None

    return parse_int(value.get("min")), parse_int(value.get("max"))


def normalize_cue_choice(value):
    raw = str(value or "").strip().upper()
    compact = raw.replace(" ", "").replace("-", "").replace("_", "").replace("!", "")

    if compact in ("SONG", "PLAYSONG", "PLAYASONG"):
        return "SONG"
    if compact in ("NAMES", "CALLNAMES", "CALLINGNAMES", "NAMECALLING"):
        return "NAMES"
    if compact in ("EITHER", "PLAYORCALL", "SONGORNAMES", "SONGORCALL"):
        return "EITHER"

    return None


def clean_matched_preference(value):
    raw = str(value or "").strip()
    return raw or None


def clean_preference_text(value):
    return " ".join(str(value or "").strip().lower().replace("\n", " ").split())


def is_no_help_preference(value):
    return clean_preference_text(value) == "no help at all, i'll steer the convo"


def is_small_icebreaker_preference(value):
    return clean_preference_text(value) == "to be given a small ice breaker"


def is_short_game_preference(value):
    return clean_preference_text(value) == "play a short game together, on the hub"


def is_long_game_preference(value):
    return clean_preference_text(value) == "play a longer game on the hub"


def is_known_matched_preference(value):
    return (
        is_no_help_preference(value)
        or is_small_icebreaker_preference(value)
        or is_short_game_preference(value)
        or is_long_game_preference(value)
    )


def accepted_genders_for(user):
    gender = user.get("gender")
    orientation = user.get("orientation")

    if not gender or not orientation:
        return set()

    if orientation == "HETEROSEXUAL":
        if gender == "MAN":
            return {"WOMAN"}
        if gender == "WOMAN":
            return {"MAN"}
        return set()

    if orientation == "HOMOSEXUAL":
        return {gender}

    if orientation in ("BISEXUAL", "PANSEXUAL"):
        return {"MAN", "WOMAN", "OTHER"}

    return set()


def user_is_interested_in(user, candidate):
    return candidate.get("gender") in accepted_genders_for(user)


def age_is_compatible(user, candidate):
    candidate_age = candidate.get("age")
    min_age = user.get("matchMinAge")
    max_age = user.get("matchMaxAge")

    if candidate_age is None or min_age is None or max_age is None:
        return False

    return min_age <= candidate_age <= max_age


def cue_choices_are_compatible(user_a, user_b):
    cue_a = user_a.get("cueChoice")
    cue_b = user_b.get("cueChoice")

    if not cue_a or not cue_b:
        return False

    return cue_a == cue_b or cue_a == "EITHER" or cue_b == "EITHER"


def matched_preferences_are_compatible(user_a, user_b):
    preference_a = user_a.get("matchedPreference")
    preference_b = user_b.get("matchedPreference")

    if (
        not is_known_matched_preference(preference_a)
        or not is_known_matched_preference(preference_b)
    ):
        return False

    if is_no_help_preference(preference_a) or is_no_help_preference(preference_b):
        return is_no_help_preference(preference_a) and is_no_help_preference(preference_b)
    if is_long_game_preference(preference_a) or is_long_game_preference(preference_b):
        return is_long_game_preference(preference_a) and is_long_game_preference(preference_b)

    return (
        is_small_icebreaker_preference(preference_a)
        or is_short_game_preference(preference_a)
    ) and (
        is_small_icebreaker_preference(preference_b)
        or is_short_game_preference(preference_b)
    )


def users_are_compatible(user_a, user_b):
    a_wants_b = user_is_interested_in(user_a, user_b)
    b_wants_a = user_is_interested_in(user_b, user_a)
    ages_match = (
        age_is_compatible(user_a, user_b)
        and age_is_compatible(user_b, user_a)
    )
    cue_choices_match = cue_choices_are_compatible(user_a, user_b)
    matched_preferences_match = matched_preferences_are_compatible(user_a, user_b)

    return (
        a_wants_b
        and b_wants_a
        and ages_match
        and cue_choices_match
        and matched_preferences_match
    )


def build_active_user(document_id, data, rfid_epc):
    gender = normalize_gender(data.get("gender") or data.get("identity"))
    orientation = normalize_orientation(data.get("orientation") or data.get("lookingFor"))
    age = parse_int(data.get("age"))
    match_min_age, match_max_age = parse_age_range(data.get("matchAgeRange"))
    cue_choice = normalize_cue_choice(data.get("cueChoice"))
    matched_preference = clean_matched_preference(data.get("matchedPreference"))

    if not all([
        gender,
        orientation,
        age,
        match_min_age,
        match_max_age,
        cue_choice,
        matched_preference,
    ]):
        return None

    if not is_known_matched_preference(matched_preference):
        return None

    display_name = (
        data.get("name")
        or data.get("nickname")
        or data.get("displayName")
        or data.get("firstName")
        or data.get("username")
        or f"profile-{document_id[:8]}"
    )

    return {
        "documentId": document_id,
        "name": str(display_name).strip() or f"profile-{document_id[:8]}",
        "age": age,
        "gender": gender,
        "orientation": orientation,
        "matchMinAge": match_min_age,
        "matchMaxAge": match_max_age,
        "cueChoice": cue_choice,
        "matchedPreference": matched_preference,
        "nfcUid": data.get("nfcUid"),
        "rfidEpc": rfid_epc,
        "soundCloudTrack": data.get("soundCloudTrack"),
    }


def match_user_payload(user):
    return {
        "profileId": user["documentId"],
        "name": user["name"],
        "age": user["age"],
        "gender": user["gender"],
        "orientation": user["orientation"],
        "matchAgeRange": {
            "min": user["matchMinAge"],
            "max": user["matchMaxAge"],
        },
        "cueChoice": user["cueChoice"],
        "matchedPreference": user["matchedPreference"],
        "nfcUid": user.get("nfcUid"),
        "rfidEpc": user["rfidEpc"],
        "soundCloudTrack": user.get("soundCloudTrack"),
    }


def persist_match(db, user_a, user_b):
    match_ref = db.collection("matches").document()
    matched_at = firestore.SERVER_TIMESTAMP
    user_a_ref = db.collection("profiles").document(user_a["documentId"])
    user_b_ref = db.collection("profiles").document(user_b["documentId"])

    match_payload = {
        "status": PROFILE_MATCHED_STATUS,
        "createdAt": matched_at,
        "profileIds": [
            user_a["documentId"],
            user_b["documentId"],
        ],
        "rfidEpcs": [
            user_a["rfidEpc"],
            user_b["rfidEpc"],
        ],
        "nfcUids": [
            user_a.get("nfcUid"),
            user_b.get("nfcUid"),
        ],
        "users": [
            match_user_payload(user_a),
            match_user_payload(user_b),
        ],
        "cueChoice": user_a["cueChoice"]
        if user_a["cueChoice"] == user_b["cueChoice"]
        else "EITHER",
        "matchedPreference": user_a["matchedPreference"],
    }

    batch = db.batch()
    batch.set(match_ref, match_payload)
    batch.set(
        user_a_ref,
        {
            "status": PROFILE_MATCHED_STATUS,
            "matchId": match_ref.id,
            "matchedProfileId": user_b["documentId"],
            "matchedAt": matched_at,
            "updatedAt": matched_at,
        },
        merge=True,
    )
    batch.set(
        user_b_ref,
        {
            "status": PROFILE_MATCHED_STATUS,
            "matchId": match_ref.id,
            "matchedProfileId": user_a["documentId"],
            "matchedAt": matched_at,
            "updatedAt": matched_at,
        },
        merge=True,
    )
    batch.commit()

    print(f"Firebase match written: matches/{match_ref.id}")
    return match_ref.id


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

            if change.type.name in ("ADDED", "MODIFIED") and status == PROFILE_READY_STATUS:
                user = build_active_user(
                    document_id=change.document.id,
                    data=data,
                    rfid_epc=rfid_epc,
                )

                if user is None:
                    active_users_by_epc.pop(rfid_epc, None)
                    print(
                        "PROFILE SKIPPED, INCOMPLETE MATCHING FIELDS:",
                        change.document.id,
                        "/",
                        rfid_epc,
                    )
                    continue

                active_users_by_epc[rfid_epc] = user

                print(
                    "READY USER:",
                    user["name"],
                    "/",
                    rfid_epc,
                    "/",
                    user["gender"],
                    "/",
                    user["orientation"],
                    "/ age",
                    user["age"],
                    "/ wants",
                    f"{user['matchMinAge']}-{user['matchMaxAge']}",
                    "/ cue",
                    user["cueChoice"],
                    "/ matched",
                    user["matchedPreference"],
                )

            else:
                active_users_by_epc.pop(rfid_epc, None)
                print(f"PROFILE REMOVED FROM READY CACHE: {rfid_epc}")

        print(f"Ready cloud users: {len(active_users_by_epc)}")


def start_firestore_listener(db):
    query = db.collection("profiles").where("status", "==", PROFILE_READY_STATUS)
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


def maybe_create_match(db):
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
            f"{user_a['name']} ({user_a['gender']}, {user_a['orientation']}, "
            f"{user_a['age']}) <-> "
            f"{user_b['name']} ({user_b['gender']}, {user_b['orientation']}, "
            f"{user_b['age']})"
        )
        print(f"EPC A: {user_a['rfidEpc']}")
        print(f"EPC B: {user_b['rfidEpc']}")
        print()

        try:
            match_id = persist_match(db, user_a, user_b)
            user_a["matchId"] = match_id
            user_b["matchId"] = match_id
        except Exception as error:
            print(f"Could not write match to Firebase: {error}")

        return matched_pair


def run_wristband_led_alert(reader, user_a, user_b):
    selected_epcs = [
        user_a["rfidEpc"],
        user_b["rfidEpc"],
    ]

    reader.initialise()
    print("Match alert: alternating matched wristband LED alerts...")

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


def run_match_alert(reader, user_a, user_b):
    run_wristband_led_alert(reader, user_a, user_b)


def r200_loop(db):
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

                pair = maybe_create_match(db)

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
    print(f"Listening for {PROFILE_READY_STATUS} profiles...")

    reset_thread = threading.Thread(target=reset_socket_loop, daemon=True)
    reset_thread.start()

    r200_thread = threading.Thread(target=r200_loop, args=(db,), daemon=True)
    r200_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
        watch.unsubscribe()


if __name__ == "__main__":
    main()
