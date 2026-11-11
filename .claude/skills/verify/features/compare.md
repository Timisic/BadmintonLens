# Compare

## Sub-features
- Two pickers, coach and mine. Options read `<机位> · <视频名> · <击球时间>`, partners from the same side first, the rest marked `（不同侧）`.
- Either side leads. Picking mine moves the coach to its best match. Picking a coach moves mine to the swing that coach suits best.
- Tab 逐帧: nine stills per row at the same seconds from the hit, coach above me. The centre column is `击球点`.
- Tab 同步慢放: both swings side by side on one clock, looping from −0.9 s to +0.7 s around the hit, at 0.5×, 0.25× or 0.1×. One scrubber and one pair of step buttons move both.
- A notice when the two cameras differ, and another when the two swings are from different sides.

## How to get to it (user POV)
Sidebar 对比. Or the 对比 button on a usable swing in review. URL: `/compare?swing=<mine>&coach=<coach>`, either or both.

## Driving it with shoot.mjs
```bash
node .claude/skills/verify/shoot.mjs compare-slow /compare --do '
  await page.waitForTimeout(1500)
  await page.getByRole("tab", { name: "同步慢放" }).click()
  await page.waitForTimeout(1200)
  await page.getByRole("button", { name: "同步播放" }).click()
  await page.waitForTimeout(2000)
  return JSON.stringify(await page.evaluate(() => [...document.querySelectorAll("video")].filter(v => v.offsetParent).map(v => v.currentTime)))'
```
Proof for playback: subtract each swing's `hit` (from `/api/compare`) from the two times; the two offsets agree within a frame. Proof for stills: the `击球点` column reads `0.00s` in both rows and shows the racket arm at full reach in both.

Pickers: `getByRole("combobox", { name: "选教练的一拍" })` and `"选我的一拍"`, then `getByRole("option", { name: /背后/ })`.

## Gotchas
- The hit time comes from the label, corrected by `compare.py refine` from the racket wrist in `pose.npz`. A swing a person labeled is never corrected.
- The crop comes from `pose.npz` too. Without it the cell shows the swing's looser box and the player looks small.
- Comparable means usable with a hit. Coach swings must also be in a `demo` segment.
- A coach view nobody of mine was filmed from still shows, with the different-side notice.
- Under about 800px the stills keep their width and scroll sideways.
- Do not leave a picker open at the end of `--do`: the screenshot waits on it.
