---
name: clean-coach-video
description: Clean a badminton coach video into the swing library (segments, swings, phases, camera side) with clean.py, then review the model's labels as the vision reviewer. Use when asked to clean, ingest, re-run, or review a coach video, or to fix swing labels in work/<video>/.
---

# Clean a coach video

Run from the `proto/` directory. The video path is `<video>` below. Every stage caches in `work/<stem>/` and is safe to re-run.

## 1. Model pass (Qwen, cheap)

The model reads `DASHSCOPE_API_KEY` from the environment. If it is unset, ask the user to export it. Never write a key into a file or repeat it in a reply.

```bash
python3 clean.py prep "<video>"
python3 clean.py classify "<video>"
python3 clean.py swings "<video>"
python3 clean.py phases "<video>"
python3 clean.py fine "<video>" --model
python3 clean.py table "<video>"
```

After `swings`, glance at the printed segment list. Re-running `swings` gives segments new ids, so re-run `phases`, `fine` and `table` after it.

`phases` makes two calls per swing. The main call asks for racket height per sheet row and the phase frames. Code then sets `usable` false when the racket never comes down from above, and drops `置信度` to 低 when the phase order is wrong. A separate short call asks only `脸` and `拍位`, because folded into the main call those answers were wrong half the time.

## 2. Review pass (you)

`table` writes `work/<stem>/claude_review_task.md` and `work/<stem>/review_sides.jpg`. The task has two lists.

**Segment types.** Each demo segment with its transcript and sheets. Check that `全速正确示范` really is full speed. Slow-motion breakdowns become `慢速分解` and match footage becomes `比赛实战`.

**Swings.** Every usable or low-confidence swing with the model's labels. Read `review_sides.jpg` first. It shows the backswing of every listed swing with its `脸` and `拍位`, so one look fixes most side errors. Then Read `swings/<id>.jpg` for each id, and `fine/<id>.jpg` only when the hit frame looks wrong.

- `脸`: 看得到 when the coach's eyes and nose are visible, 看不到 when only the back of the head is.
- `拍位`: 画面左 or 画面右, the racket's side of the body from the viewer's left and right, not the coach's.
- `angle`: camera position relative to the coach. One of 正面 / 背后 / 斜后 / 侧面 / 斜前.
- `usable` false: the racket never comes down from above the head to the front, as when the coach only raises the racket, walks, or gestures.
- Frame fields `引拍侧身`, `拍头最低点`, `击球点`: use the yellow `#` numbers on the tiles. Keep them in that order.

Write `work/<stem>/claude_labels.json`:

```json
{"seg092_sw0": {"usable": true, "脸": "看不到", "拍位": "画面右"},
 "seg089": {"type": "慢速分解"}}
```

`usable` is required on every swing entry and `type` on every segment entry, even when unchanged, because a model re-run can flip them. Other fields only when you change them. Then re-run `table`. It merges your fields over the model's, marks them `复核: "claude"`, warns about ids that match nothing, and drops reviewed ids from the task.

With more than 10 swings, split the ids across subagents. Each writes `claude_labels_<n>.json`. Merge them into `claude_labels.json` yourself, then delete the parts.

Change no file other than `claude_labels.json`.

## 3. Output

`work/<stem>/segments.json` is the library record the frontend reads. Keep its shape. Add fields only, and rename or remove none.

```
{video, fps, segments: [{id, type, angle, t0, t1, text, clip, 复核?, swings: [
  {id, peak_frame, t, sheet, box, phases: {usable, angle, 脸, 拍位, 引拍侧身, 拍头最低点, 击球点, 随挥收拍,
                                           置信度, 备注, 拍头高度, 精标?, 复核?}}]}]}
```

Label layers merge in this order, later wins: `phase_labels.json` (model), `fine_labels.json` (fine hit frames), `claude_labels.json` (you). `segments_confirmed.json`, saved by `python3 clean.py review "<video>"`, holds human edits. No code merges it yet.

User-side comparison picks coach swings from every `work/*/segments.json`. It requires the same `脸` and `拍位`, prefers the same `angle`, then fine-labeled, confident, and high-fps swings. Run `python3 compare_angle.py` after the library changes.
