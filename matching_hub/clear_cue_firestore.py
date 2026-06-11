import argparse
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore


DEFAULT_COLLECTIONS = [
    "profiles",
    "wristbands",
    "matchingQueue",
    "matches",
]

CONFIRM_TEXT = "DELETE_CUE_DATA"
BATCH_SIZE = 250


def initialise_firestore(service_account_path):
    cred = credentials.Certificate(str(service_account_path))
    firebase_admin.initialize_app(cred)
    return firestore.client()


def delete_document_recursive(document_ref, dry_run):
    deleted_count = 0

    for subcollection_ref in document_ref.collections():
        deleted_count += delete_collection_recursive(subcollection_ref, dry_run)

    print(f"{'Would delete' if dry_run else 'Deleting'} document: {document_ref.path}")

    if not dry_run:
        document_ref.delete()

    return deleted_count + 1


def delete_collection_recursive(collection_ref, dry_run):
    total_deleted = 0

    while True:
        docs = list(collection_ref.limit(BATCH_SIZE).stream())

        if not docs:
            break

        for doc in docs:
            total_deleted += delete_document_recursive(doc.reference, dry_run)

        if dry_run:
            break

    return total_deleted


def clear_collections(db, collection_names, dry_run):
    grand_total = 0

    for collection_name in collection_names:
        print()
        print(f"Scanning collection: {collection_name}")

        collection_ref = db.collection(collection_name)
        deleted_count = delete_collection_recursive(collection_ref, dry_run)
        grand_total += deleted_count

        print(
            f"{'Would delete' if dry_run else 'Deleted'} "
            f"{deleted_count} document(s) from {collection_name}"
        )

    return grand_total


def parse_args():
    parser = argparse.ArgumentParser(
        description="Clear Cue Firestore user and wristband data."
    )
    parser.add_argument(
        "--service-account",
        default="serviceAccountKey.json",
        help="Path to Firebase service account JSON.",
    )
    parser.add_argument(
        "--collections",
        nargs="+",
        default=DEFAULT_COLLECTIONS,
        help="Firestore collections to clear.",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help=f"Required to delete data. Use: {CONFIRM_TEXT}",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    dry_run = args.confirm != CONFIRM_TEXT
    service_account_path = Path(args.service_account).expanduser()

    if not service_account_path.exists():
        raise FileNotFoundError(
            f"Service account file not found: {service_account_path}"
        )

    print("Cue Firestore cleanup tool")
    print(f"Service account: {service_account_path}")
    print(f"Collections: {', '.join(args.collections)}")

    if dry_run:
        print()
        print("DRY RUN ONLY. No Firebase data will be deleted.")
        print(f"To delete data, rerun with: --confirm {CONFIRM_TEXT}")
    else:
        print()
        print("CONFIRMED DELETE. Firestore data will be deleted.")

    db = initialise_firestore(service_account_path)
    total = clear_collections(
        db=db,
        collection_names=args.collections,
        dry_run=dry_run,
    )

    print()
    print(f"{'Would delete' if dry_run else 'Deleted'} {total} total document(s).")


if __name__ == "__main__":
    main()
