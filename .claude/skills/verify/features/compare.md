# Compare

## Sub-features
- Camera toggle at the top right, only the cameras my swings have. Under it two strips of small pictures grouped by video: 我 (my swings from that camera) and 教练 (the demos from the same camera, best first).
- Either side leads. `?coach=<id>` alone brings one of my swings filmed from the same place.
- Tab 逐帧: seven stills per row at the same seconds from the hit, coach above me. The centre column is `击球`.
- Tab 同步慢放: both swings side by side on one clock, looping from −0.9 s to +0.7 s around the hit, at 0.5×, 0.25× or 0.1×.
- Section 差在哪: one card per finding with the fault as title, a still of each side with a ring on the joint, a bar per side, how many swings of the same video show it, and up to three passages of a coach explaining it (text plus the source video at that time, with sound). A last line lists the checks that are close to the coach.

## How to get to it (user POV)
Sidebar 对比. Or the 对比 button on a swing page. URL: `/compare?swing=<mine>&coach=<coach>`, either or both.

## Driving it with shoot.mjs
```bash
node .claude/skills/verify/shoot.mjs compare /compare --full --do '
  await page.waitForTimeout(3000)
  return [await page.locator("article h3").allTextContents(),
    await page.locator("article video").evaluateAll(v => v.map(x => [x.readyState, Math.round(x.currentTime)]))]'
```
Proof for the findings: the titles match `/api/diagnose?me=&coach=` entries with `short: true`, and each lesson video sits at its `t0`. Proof for playback: in 同步慢放 press `同步播放`, then subtract each swing's `hit` from the two visible videos' times; the offsets agree within a frame.

Pickers: `getByRole("radio", { name: "背后" })` for the camera, `getByRole("radiogroup", { name: "选我的一拍" }).getByRole("radio").nth(i)` for a swing.

## Gotchas
- Usable, hit and camera come from `compare.py refine` reading `pose.npz`. Whatever a person set wins.
- Seen from behind the pose sometimes swaps left and right. Such a swing is not measured and the section says `姿态读不准`.
- Lesson videos need the source file (`?sound=1`); `play.mp4` is silent and is the fallback.
- Under about 700px the stills keep their width and scroll sideways.
