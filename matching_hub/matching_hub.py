import threading
import time

import firebase_admin
from firebase_admin import credentials, firestore

from r200_reader import R200Reader, normalize_epc


SERVICE_ACCOUNT_PATH = "serviceAccountKey.json"
POLL_INTERVAL = 0.1

active_users_by_epc = {}
entered_users_by_epc = {}
matched_pair = None

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


def find_first_match():
    users = list(entered_users_by_epc.values())

    for i, user_a in enumerate(users):
        for user_b in users[i + 1 :]:
            if users_are_compatible(user_a, user_b):
                return user_a, user_b

    return None


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


def r200_loop():
    reader = R200Reader()
    reader.connect()
    reader.initialise()

    print("R200 scanning all tags...")

    while True:
        try:
            with state_lock:
                pair = matched_pair

            if pair is not None:
                break

            tags = reader.inventory_once()

            for tag in tags:
                note_entered_range(tag)

            pair = maybe_create_match()

            if pair is not None:
                break

            time.sleep(POLL_INTERVAL)

        except Exception as error:
            print(f"R200 scan loop error: {error}")
            time.sleep(1)

    user_a, user_b = pair
    selected_epcs = [
        user_a["rfidEpc"],
        user_b["rfidEpc"],
    ]

    reader.select_epcs(selected_epcs)
    print("Continuously inventorying matched selected tags for LED alert...")

    while True:
        try:
            tags = reader.inventory_once()
            seen_epcs = {
                normalize_epc(tag["epc"])
                for tag in tags
            }

            for epc in selected_epcs:
                if normalize_epc(epc) in seen_epcs:
                    print(f"SELECTED TAG SEEN: {epc}")

            time.sleep(POLL_INTERVAL)

        except Exception as error:
            print(f"Selected tag loop error: {error}")
            time.sleep(1)


def main():
    print("Cue matching hub starting...")

    db = initialise_firestore()
    watch = start_firestore_listener(db)
    print("Listening for ACTIVE profiles...")

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
