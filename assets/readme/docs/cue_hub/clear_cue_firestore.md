# `clear_cue_firestore.py`

Purpose: Firestore cleanup tool for demos.

This script deletes development/demo data from selected Firestore collections.

## Default Collections

- `profiles`
- `wristbands`
- `matchingQueue`
- `matches`

## Service Account

By default it looks for `serviceAccountKey.json` in the current working directory. You can also pass:

```bash
python3 clear_cue_firestore.py --service-account /path/to/serviceAccountKey.json
```

Use `--dry-run` to preview deletions.

