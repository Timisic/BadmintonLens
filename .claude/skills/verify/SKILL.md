---
name: verify
description: Drive the BadmintonLens web frontend (web/, React on Vite) and its FastAPI backend (proto/api.py) in a real Chrome against a scratch copy of the store, and capture screenshots as proof. Use after any change to web/ or proto/api.py, before calling UI work done, or when asked to check a page.
---

# Verify BadmintonLens

The app is a local web tool with three pages: library, swings, compare. This skill starts an isolated instance, drives it with Playwright in system Chrome, and leaves screenshots in `.verify/evidence/`.

All paths are from the repo root. The instance never touches `proto/store`. It works on a copy in `.verify/store`, so saving labels in a journey is safe.

## Launch

```bash
.claude/skills/verify/run.sh up
```

It copies `proto/store` to `.verify/store`, starts the API on `127.0.0.1:8765` and Vite on `localhost:5273`, and returns once both answer. Needs `pnpm install` in `web/` and `fastapi`, `uvicorn` for `python3`. Logs are `.verify/api.log` and `.verify/web.log`. The default ports 8000 and 5173 stay free for the user's own instance.

## Doctor

```bash
.claude/skills/verify/run.sh doctor
```

Prints `OK <url> videos N swings N human labels N`, or says which process is down. Run it first when anything looks off. `human labels` should be 0 on a fresh copy.

## Drive

```bash
node .claude/skills/verify/shoot.mjs <name> <path> [--dark] [--mobile] [--full] [--do '<js>']
```

It opens `<path>` at 1440×900, runs the optional `--do` body with a Playwright `page`, prints what the body returns, saves `.verify/evidence/<name>.png`, and exits 1 on any console or page error. Use Chrome, not bundled Chromium: a video without a `play.mp4` browser copy falls back to its source, and phone sources are HEVC.

Get real ids from `curl -s localhost:8765/api/library`. In zsh, unquoted variables do not split, so pass ids one by one.

Stable handles: roles and Chinese names. `getByRole('button', { name: '设为当前帧' })`, `'上一帧'`, `'下一帧'`, `'跳到击球点'`, `'删除'`, `'恢复'`, `getByRole('radio', { name: '左侧面' })`. Keys on a swing page: `ArrowLeft`/`ArrowRight` frame, `Space` play.

`node .claude/skills/verify/time.mjs <path> [runs]` prints the milliseconds from navigation until every `<video>` on the page shows its frame. The compare page with 14 stills, the finding stills and the lesson videos takes about 1.4 s on this machine once warm (the first load after a restart is slower); treat a jump well past that as a regression.

The API also serves `web/dist` on its own port, so `http://127.0.0.1:8765/` is the built app after `pnpm build`.

Per-feature journeys are in [features/](features/README.md).

## Evidence

A proof is a screenshot of the action's result plus the side effect read back from the API, for example `label.source == "human"` in `/api/library` after a save. Take the real path through the UI. Do not call the label endpoints directly to fake a save. Videos need about a second after navigation before the frame is painted, so wait in `--do` before the shot.

## Cleanup

```bash
.claude/skills/verify/run.sh down
```

Stops the two processes it started, by pid, and deletes the scratch store. `.verify/evidence/` stays.
