# Compare

## Sub-features
- Pick one of my usable swings. The backend picks the coach demo with the same camera.
- One grid, all phases at once: coach row on top, my row below, one column per phase. The caption is the offset from the hit.
- Hover a cell to step that cell one frame back or forward.

## How to get to it (user POV)
Sidebar 对比. Or the 对比 button on a reviewed user swing.

## Driving it with shoot.mjs
```bash
node .claude/skills/verify/shoot.mjs compare '/compare?swing=<userSwingId>' --do 'await page.waitForTimeout(2500)'
```
Proof: two rows of pictures with the player in frame, the hit column reads `0.00s` in both rows, and everything fits in 1440×900.

## Gotchas
- Only user swings that are usable and have backswing, racket low and hit can be compared. Others never appear in the picker.
- No coach demo with a matching camera gives a dashed notice and my row alone.
