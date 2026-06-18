from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import credentials, firestore


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ACCOUNT_PATH = Path(
    os.environ.get("FIREBASE_SERVICE_ACCOUNT", SCRIPT_DIR / "serviceAccountKey.json")
)
PROFILE_READY_STATUSES = {
    status.strip()
    for status in os.environ.get(
        "CUE_WINDOWS_MATCH_PROFILE_STATUSES",
        "ONBOARDING_SUBMITTED,WRISTBAND_SCANNED",
    ).split(",")
    if status.strip()
}
PROFILE_MATCHED_STATUS = os.environ.get("CUE_PROFILE_MATCHED_STATUS", "MATCHED")

active_users_by_profile_id: dict[str, dict[str, Any]] = {}
matched_profile_ids: set[str] = set()
state_lock = threading.RLock()


def initialise_firestore():
    if not firebase_admin._apps:
        cred = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
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
    return (
        user_is_interested_in(user_a, user_b)
        and user_is_interested_in(user_b, user_a)
        and age_is_compatible(user_a, user_b)
        and age_is_compatible(user_b, user_a)
        and cue_choices_are_compatible(user_a, user_b)
        and matched_preferences_are_compatible(user_a, user_b)
    )


def build_active_user(document_id, data):
    gender = normalize_gender(data.get("gender") or data.get("identity"))
    orientation = normalize_orientation(data.get("orientation") or data.get("lookingFor"))
    age = parse_int(data.get("age"))
    match_min_age, match_max_age = parse_age_range(data.get("matchAgeRange"))
    cue_choice = normalize_cue_choice(data.get("cueChoice"))
    matched_preference = clean_matched_preference(data.get("matchedPreference"))

    if not all(
        [
            gender,
            orientation,
            age,
            match_min_age,
            match_max_age,
            cue_choice,
            matched_preference,
        ]
    ):
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
        "rfidEpc": data.get("rfidEpc"),
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
        "rfidEpc": user.get("rfidEpc"),
        "soundCloudTrack": user.get("soundCloudTrack"),
    }


def find_first_match():
    users = list(active_users_by_profile_id.values())

    for index, user_a in enumerate(users):
        if user_a["documentId"] in matched_profile_ids:
            continue

        for user_b in users[index + 1:]:
            if user_b["documentId"] in matched_profile_ids:
                continue

            print(
                "CHECKING MATCH:",
                f"{user_a['name']} + {user_b['name']}",
                "/",
                f"{user_a['matchedPreference']} + {user_b['matchedPreference']}",
            )

            if users_are_compatible(user_a, user_b):
                return user_a, user_b

    return None


def persist_match(db, user_a, user_b):
    match_ref = db.collection("matches").document()
    matched_at = firestore.SERVER_TIMESTAMP
    user_a_ref = db.collection("profiles").document(user_a["documentId"])
    user_b_ref = db.collection("profiles").document(user_b["documentId"])

    match_payload = {
        "status": PROFILE_MATCHED_STATUS,
        "source": "windows_matcher",
        "createdAt": matched_at,
        "profileIds": [user_a["documentId"], user_b["documentId"]],
        "rfidEpcs": [user_a.get("rfidEpc"), user_b.get("rfidEpc")],
        "nfcUids": [user_a.get("nfcUid"), user_b.get("nfcUid")],
        "users": [match_user_payload(user_a), match_user_payload(user_b)],
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
    return match_ref.id


def maybe_create_match(db):
    with state_lock:
        pair = find_first_match()
        if pair is None:
            return

        user_a, user_b = pair
        matched_profile_ids.add(user_a["documentId"])
        matched_profile_ids.add(user_b["documentId"])

    print()
    print("MATCH FOUND")
    print(
        f"{user_a['name']} ({user_a['gender']}, {user_a['orientation']}, {user_a['age']})"
        " <-> "
        f"{user_b['name']} ({user_b['gender']}, {user_b['orientation']}, {user_b['age']})"
    )

    try:
        match_id = persist_match(db, user_a, user_b)
        print(f"Match written to Firestore: matches/{match_id}")
    except Exception as error:
        print(f"Could not write match to Firebase: {error}")
        with state_lock:
            matched_profile_ids.discard(user_a["documentId"])
            matched_profile_ids.discard(user_b["documentId"])


def handle_profiles_snapshot(db, docs, changes, read_time):
    del docs, read_time

    changed = False

    with state_lock:
        for change in changes:
            data = change.document.to_dict() or {}
            document_id = change.document.id
            status = data.get("status")

            if change.type.name not in ("ADDED", "MODIFIED"):
                active_users_by_profile_id.pop(document_id, None)
                changed = True
                continue

            if status == PROFILE_MATCHED_STATUS:
                active_users_by_profile_id.pop(document_id, None)
                matched_profile_ids.add(document_id)
                changed = True
                continue

            if status not in PROFILE_READY_STATUSES:
                active_users_by_profile_id.pop(document_id, None)
                changed = True
                continue

            user = build_active_user(document_id, data)

            if user is None:
                active_users_by_profile_id.pop(document_id, None)
                print("PROFILE SKIPPED, INCOMPLETE MATCHING FIELDS:", document_id)
                changed = True
                continue

            active_users_by_profile_id[document_id] = user
            changed = True
            print(
                "READY USER:",
                user["name"],
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

        print(f"Ready Windows users: {len(active_users_by_profile_id)}")

    if changed:
        maybe_create_match(db)


def start_profile_listener(db):
    def on_profiles_snapshot(docs, changes, read_time):
        handle_profiles_snapshot(db, docs, changes, read_time)

    return db.collection("profiles").on_snapshot(on_profiles_snapshot)


def main():
    print("Cue Windows Matcher")
    print("=" * 24)
    print(f"Service account: {SERVICE_ACCOUNT_PATH}")
    print(f"Ready statuses: {sorted(PROFILE_READY_STATUSES)}")
    print(f"Matched status: {PROFILE_MATCHED_STATUS}")

    db = initialise_firestore()
    watch = start_profile_listener(db)
    print("Listening for Android-created profiles. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Windows matcher...")
        watch.unsubscribe()


if __name__ == "__main__":
    main()
