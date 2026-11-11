---
name: clean-coach-video
description: Clean a badminton video into the swing library with clean.py, doing the vision labeling yourself through subagents. Covers coach videos (segments, swings, phases, camera side) and the user's own clips. Use when asked to clean, ingest, process, re-run, or relabel a video, or to fix swing labels in store/<role>/<video name>/.
---

# Clean a video into the swing library

Run from `proto/`. `<video>` is the video path. Each stage caches in `store/coach/<file name>/` or `store/user/<file name>/` and is safe to re-run. Sheets and clips are named by their time in the video, such as `swings/01m04.167s.jpg`. Labels are keyed by swing id, which `swings.json` maps to each sheet. The code calls no model. You are the vision model, so every label comes from you or a subagent reading a sheet image.

Field names and values are English and come from the vocab tables at the top of `db.py`. Frame numbers in a label are the yellow `#` numbers on the sheet. `ingest` turns them into seconds.

## Coach video

1. `python3 clean.py prep "<video>"`. Read `classify_task.md`. For each `sheets/sheet_XX.jpg` with its `.txt`, label every tile. Write all tiles to `tile_labels.json`.
2. `python3 clean.py swings "<video>"`. Glance at the printed segment list. Read `phase_task.md`. For each sheet listed in `swings.json`, write its answer to `phase_labels.json` under the swing id.
3. `python3 clean.py fine "<video>"`. Read `fine_task.md`. It lists each `fine/<time>.jpg` with its swing id. Write each answer to `fine_labels.json`. These override `racket_low` and `hit` from step 2.
4. `python3 clean.py ingest "<video>"`. It validates every label and names each one it rejects. Fix those entries and run it again.

To change a segment's kind after seeing its swings, write `segment_kinds.json` as `{"<segment id>": "slow_demo"}` and re-run `ingest`. Changing `tile_labels.json` instead means re-running `swings` and relabeling.

## The user's own clip

`python3 clean.py prep "<video>" --user`, then steps 2 to 4. There is no classify step. Most candidates in a user clip are walking or setup. Mark those `{"usable": false}` and nothing else.

## Labeling

- With more than 10 sheets, split them across subagents. Each writes `<name>_<n>.json`. Merge the parts into the final file yourself, then delete the parts.
- `usable` is false when the racket never comes down from above the head to the front, as when the player only raises the racket, walks, or gestures. A usable swing needs `backswing`, `racket_low` and `hit`.
- `face_visible` and `racket_side` decide which coach swing a user swing is compared with. Judge both from the first row only. `racket_side` is the viewer's left or right, not the player's.
- `ingest` sets `usable` to false when `racket_height` does not end lower than it starts.

## After

- `python3 compare.py` rebuilds the comparison images in `store/compare/`.
- `python3 db.py` prints the library as JSON.
- `LENS_REMOTE=ubuntu-8-179:badminton-lens/store python3 store.py push` copies the store to the intranet server. Use SSH key auth only. Never type or store a password.
