# Library

## Sub-features
- Table of videos with role, cameras, duration, swing count. Sortable.
- Video page with two tabs: swings (contact sheets) and segments (clips with transcript).

## How to get to it (user POV)
Sidebar 素材库. Click a row to open the video. Click a swing to open its swing page.

## Driving it with shoot.mjs
```bash
node .claude/skills/verify/shoot.mjs lib /
node .claude/skills/verify/shoot.mjs video /videos/<videoId>
```
Proof: the row count matches `videos` from doctor, and the swing tab count matches that video's swings.

## Gotchas
- Contact sheets and clips come from `/store/...`. A missing file shows as a broken image, not a console error.
